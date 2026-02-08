import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
import pytesseract
from pdf2image import convert_from_path

from app.backend.database import (
    clear_index,
    file_already_indexed,
    store_file,
    store_page,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path("/data")
MIN_TEXT_LENGTH = 50

_current_dir: Path = DATA_DIR


def get_current_dir() -> str:
    """Return relative path from DATA_DIR (empty string means root)."""
    if _current_dir == DATA_DIR:
        return ""
    return str(_current_dir.relative_to(DATA_DIR))


def set_current_dir(path: str) -> None:
    """Set current directory. Path must be a subdirectory of DATA_DIR."""
    global _current_dir
    if not path:
        _current_dir = DATA_DIR
        return
    target = (DATA_DIR / path).resolve()
    if not str(target).startswith(str(DATA_DIR.resolve())):
        raise ValueError("Path must be within /data")
    if not target.is_dir():
        raise ValueError(f"Directory does not exist: {path}")
    _current_dir = target


@dataclass
class IndexingStatus:
    is_running: bool = False
    total_files: int = 0
    processed_files: int = 0
    current_file: str = ""
    errors: list[str] = field(default_factory=list)


status = IndexingStatus()
_lock = asyncio.Lock()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_text_pdfplumber(page) -> str:
    text = page.extract_text() or ""
    return text.strip()


def _ocr_page_image(pdf_path: Path, page_number: int) -> str:
    images = convert_from_path(
        str(pdf_path), first_page=page_number, last_page=page_number, dpi=300
    )
    if not images:
        return ""
    return pytesseract.image_to_string(images[0], lang="pol").strip()


def _index_single_file(pdf_path: Path) -> None:
    rel_path = str(pdf_path.relative_to(_current_dir))
    file_hash = _sha256(pdf_path)

    if file_already_indexed(rel_path, file_hash):
        logger.info("Skipping (unchanged): %s", rel_path)
        return

    logger.info("Indexing: %s", rel_path)
    file_id = store_file(rel_path, file_hash)

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = _extract_text_pdfplumber(page)
                if len(text) < MIN_TEXT_LENGTH:
                    text = _ocr_page_image(pdf_path, i)
                if text:
                    store_page(file_id, i, text)
    except Exception as e:
        logger.error("Error processing %s: %s", rel_path, e)
        status.errors.append(f"{rel_path}: {e}")


def _run_indexing(full_reindex: bool = False) -> None:
    global status
    status.errors = []

    if full_reindex:
        clear_index()

    pdf_files = sorted(_current_dir.rglob("*.pdf"))
    status.total_files = len(pdf_files)
    status.processed_files = 0

    for pdf_path in pdf_files:
        status.current_file = pdf_path.name
        try:
            _index_single_file(pdf_path)
        except Exception as e:
            logger.error("Unexpected error for %s: %s", pdf_path, e)
            status.errors.append(f"{pdf_path.name}: {e}")
        status.processed_files += 1

    status.current_file = ""


async def run_indexing_async(full_reindex: bool = False) -> None:
    global status
    if _lock.locked():
        logger.warning("Indexing already in progress, skipping.")
        return

    async with _lock:
        status.is_running = True
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _run_indexing, full_reindex)
        finally:
            status.is_running = False
