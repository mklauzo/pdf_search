# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```bash
docker compose up --build        # build and start
docker compose up                # start without rebuild
docker compose down              # stop
```

Configuration via env vars or `.env` file:
- `PDF_DIR` — host directory with PDFs, mounted as `/data` in container (default: `./data`)
- `PORT` — host port (default: `8000`)

```bash
PDF_DIR=~/dokumenty PORT=8080 docker compose up --build
```

No tests or linter configured.

## Architecture

Dockerized FastAPI app that indexes local PDFs into SQLite FTS5 for full-text search, with Tesseract OCR fallback for scanned pages.

**Data flow:** PDF files in `/data` → indexer extracts text (pdfplumber) or OCRs scans (pytesseract/pdf2image) → pages stored in SQLite with FTS5 virtual table → search queries use FTS5 MATCH with snippet().

**Key design decisions:**
- Text vs OCR decided **per page** (not per file) — pages with <50 chars of extracted text fall back to OCR. This handles mixed PDFs correctly.
- File change detection uses SHA-256 hash — unchanged files are skipped on re-index.
- `check_for_changes()` in indexer compares filenames on disk vs database (no hashing) — used by frontend to enable/disable the reindex button. The button activates only when new or deleted files are detected.
- Indexing runs in a background thread via `asyncio.run_in_executor()` with an `asyncio.Lock` preventing concurrent indexing. Indexing continues server-side regardless of whether the browser is open.
- `indexer.status` is a module-level `IndexingStatus` dataclass — shared mutable state polled by the frontend and API endpoints.
- `indexer._current_dir` is module-level mutable state controlling which subdirectory of `/data` is indexed. Filenames in the database are relative to this directory.
- Database at `/data/.pdf_search_index.db` persists alongside the PDFs in the mounted volume.
- `PIL.Image.MAX_IMAGE_PIXELS` raised to 300M in indexer.py to handle large scanned pages without decompression bomb errors.
- Frontend is a single HTML file with inline CSS/JS, served as static files mounted at `/` (must be mounted **after** API routes in main.py).
- Page image rendering uses `@lru_cache(maxsize=50)` keyed on (path, page, query).

**API endpoints (defined before static mount):**
- `POST /search` — FTS5 query, returns `{results: [{file, page, snippet}]}`
- `POST /reindex` — triggers full re-index in background
- `GET /indexing-status` — polling endpoint for progress
- `GET /changes-detected` — compares disk files vs index, returns `{has_changes, new_files, deleted_files}`
- `GET /stats` — index statistics (file/page counts, chars, per-directory breakdown)
- `GET /current-directory` — returns current indexing directory
- `GET /directories` — lists subdirectories of `/data` (max 2 levels deep)
- `POST /set-directory` — changes indexing directory, clears index, triggers re-index
- `GET /page-image?file=&page=&query=` — renders PDF page as PNG (150 DPI, LRU cached, optional query term highlighting)

**System dependencies (installed in Dockerfile):** tesseract-ocr, tesseract-ocr-pol, poppler-utils.
