import asyncio
import io
import logging
from functools import lru_cache

import pdfplumber
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pdf2image import convert_from_path
from PIL import ImageDraw
from pydantic import BaseModel

from app.backend.database import get_stats, init_db, search
from app.backend.indexer import (
    DATA_DIR,
    check_for_changes,
    get_current_dir,
    run_indexing_async,
    set_current_dir,
    status,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

app = FastAPI(title="PDF Search")

DPI = 150
SCALE = DPI / 72  # pdfplumber uses 72 points/inch


class SearchRequest(BaseModel):
    query: str


class SetDirectoryRequest(BaseModel):
    path: str


@app.on_event("startup")
async def startup() -> None:
    init_db()
    asyncio.create_task(run_indexing_async())


@app.post("/search")
async def search_endpoint(req: SearchRequest):
    if not req.query.strip():
        return {"results": []}
    try:
        results = search(req.query)
    except Exception:
        return {"results": [], "error": "Invalid search query"}
    return {"results": results}


@app.post("/reindex")
async def reindex_endpoint():
    if status.is_running:
        return {"message": "Indexing already in progress"}
    asyncio.create_task(run_indexing_async(full_reindex=True))
    return {"message": "Reindexing started"}


@app.get("/indexing-status")
async def indexing_status_endpoint():
    return {
        "is_running": status.is_running,
        "total_files": status.total_files,
        "processed_files": status.processed_files,
        "current_file": status.current_file,
        "errors": status.errors,
    }


@app.get("/stats")
async def stats_endpoint():
    return get_stats()


@app.get("/current-directory")
async def current_directory_endpoint():
    rel = get_current_dir()
    full = str(DATA_DIR / rel) if rel else str(DATA_DIR)
    return {"path": rel, "full_path": full}


@app.get("/directories")
async def directories_endpoint():
    dirs: list[str] = []
    for p in sorted(DATA_DIR.rglob("*")):
        if not p.is_dir():
            continue
        rel = p.relative_to(DATA_DIR)
        if len(rel.parts) <= 2:
            dirs.append(str(rel))
    return {"directories": dirs}


@app.get("/files")
async def files_endpoint():
    from app.backend.indexer import _current_dir
    files = sorted(str(p.relative_to(_current_dir)) for p in _current_dir.rglob("*.pdf"))
    return {"files": files}


@app.get("/file-page-count")
async def file_page_count_endpoint(
    file: str = Query(..., description="Relative filename"),
):
    from app.backend.indexer import _current_dir

    pdf_path = (_current_dir / file).resolve()
    if not str(pdf_path).startswith(str(_current_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            count = len(pdf.pages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading PDF: {e}")

    return {"file": file, "page_count": count}


@app.get("/changes-detected")
async def changes_detected_endpoint():
    if status.is_running:
        return {"has_changes": False, "new_files": 0, "deleted_files": 0}
    return check_for_changes()


@app.post("/set-directory")
async def set_directory_endpoint(req: SetDirectoryRequest):
    try:
        set_current_dir(req.path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if status.is_running:
        return {"message": "Directory changed, but indexing already in progress"}
    asyncio.create_task(run_indexing_async(full_reindex=True))
    return {"message": "Directory changed, reindexing started"}


@lru_cache(maxsize=50)
def _render_page(pdf_path: str, page: int, query: str = "") -> bytes:
    images = convert_from_path(pdf_path, first_page=page, last_page=page, dpi=DPI)
    if not images:
        raise ValueError("Could not render page")

    img = images[0]

    if query:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                p = pdf.pages[page - 1]
                words = p.extract_words()
                query_terms = [t.lower() for t in query.split() if len(t) >= 2]
                draw = ImageDraw.Draw(img)
                pad = 2
                for w in words:
                    w_text = w["text"].lower()
                    if any(term in w_text for term in query_terms):
                        x0 = w["x0"] * SCALE - pad
                        y0 = w["top"] * SCALE - pad
                        x1 = w["x1"] * SCALE + pad
                        y1 = w["bottom"] * SCALE + pad
                        draw.rectangle([x0, y0, x1, y1], outline="red", width=2)
        except Exception:
            pass  # return image without highlights on error

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@app.get("/page-image")
async def page_image_endpoint(
    file: str = Query(..., description="Relative filename"),
    page: int = Query(..., gt=0, description="Page number (1-based)"),
    query: str = Query("", description="Search query for highlighting"),
):
    from app.backend.indexer import _current_dir

    pdf_path = (_current_dir / file).resolve()
    if not str(pdf_path).startswith(str(_current_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        data = await asyncio.get_event_loop().run_in_executor(
            None, _render_page, str(pdf_path), page, query.strip()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Render error: {e}")

    return StreamingResponse(io.BytesIO(data), media_type="image/png")


app.mount("/", StaticFiles(directory="app/frontend", html=True), name="frontend")
