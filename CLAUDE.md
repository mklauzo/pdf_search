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
- Indexing runs in a background thread via `asyncio.run_in_executor()` with an `asyncio.Lock` preventing concurrent indexing.
- `indexer.status` is a module-level `IndexingStatus` dataclass — shared mutable state polled by the frontend and API endpoints.
- Database at `/data/.pdf_search_index.db` persists alongside the PDFs in the mounted volume.
- Frontend is a single HTML file with inline CSS/JS, served as static files mounted at `/` (must be mounted **after** API routes in main.py).

**API endpoints (defined before static mount):**
- `POST /search` — FTS5 query, returns `{results: [{file, page, snippet}]}`
- `POST /reindex` — triggers full re-index in background
- `GET /indexing-status` — polling endpoint for progress
- `GET /current-directory` — returns current indexing directory
- `GET /directories` — lists subdirectories of `/data` (max 2 levels deep)
- `POST /set-directory` — changes indexing directory, clears index, triggers re-index
- `GET /page-image?file=&page=` — renders PDF page as PNG (150 DPI, LRU cached)

**System dependencies (installed in Dockerfile):** tesseract-ocr, tesseract-ocr-pol, poppler-utils.
