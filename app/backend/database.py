import sqlite3
from pathlib import Path

DB_PATH = Path("/data/.pdf_search_index.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pdf_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS pdf_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL REFERENCES pdf_files(id) ON DELETE CASCADE,
                page_number INTEGER NOT NULL,
                content TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS pdf_pages_fts USING fts5(
                content,
                content_rowid='id'
            );
        """)
        conn.commit()
    finally:
        conn.close()


def file_already_indexed(filename: str, file_hash: str) -> bool:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM pdf_files WHERE filename = ? AND file_hash = ?",
            (filename, file_hash),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def store_file(filename: str, file_hash: str) -> int:
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO pdf_files (filename, file_hash) VALUES (?, ?)",
            (filename, file_hash),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def store_page(file_id: int, page_number: int, content: str) -> None:
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO pdf_pages (file_id, page_number, content) VALUES (?, ?, ?)",
            (file_id, page_number, content),
        )
        page_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO pdf_pages_fts (rowid, content) VALUES (?, ?)",
            (page_id, content),
        )
        conn.commit()
    finally:
        conn.close()


def search(query: str, limit: int = 100) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT
                pf.filename,
                pp.page_number,
                snippet(pdf_pages_fts, 0, '<mark>', '</mark>', '…', 40) AS snippet
            FROM pdf_pages_fts
            JOIN pdf_pages pp ON pp.id = pdf_pages_fts.rowid
            JOIN pdf_files pf ON pf.id = pp.file_id
            WHERE pdf_pages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
        return [
            {"file": r["filename"], "page": r["page_number"], "snippet": r["snippet"]}
            for r in rows
        ]
    finally:
        conn.close()


def delete_file_by_name(filename: str) -> None:
    """Delete a file and its pages (including FTS entries) from the index."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM pdf_files WHERE filename = ?", (filename,)
        ).fetchone()
        if row is None:
            return
        file_id = row["id"]
        conn.execute(
            "DELETE FROM pdf_pages_fts WHERE rowid IN "
            "(SELECT id FROM pdf_pages WHERE file_id = ?)",
            (file_id,),
        )
        conn.execute("DELETE FROM pdf_pages WHERE file_id = ?", (file_id,))
        conn.execute("DELETE FROM pdf_files WHERE id = ?", (file_id,))
        conn.commit()
    finally:
        conn.close()


def clear_index() -> None:
    conn = _get_conn()
    try:
        conn.executescript("""
            DELETE FROM pdf_pages_fts;
            DELETE FROM pdf_pages;
            DELETE FROM pdf_files;
        """)
        conn.commit()
    finally:
        conn.close()


def get_indexed_count() -> int:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM pdf_files").fetchone()
        return row["cnt"]
    finally:
        conn.close()


def get_indexed_filenames() -> set[str]:
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT filename FROM pdf_files").fetchall()
        return {r["filename"] for r in rows}
    finally:
        conn.close()


def get_stats() -> dict:
    conn = _get_conn()
    try:
        file_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM pdf_files"
        ).fetchone()["cnt"]

        page_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM pdf_pages"
        ).fetchone()["cnt"]

        total_chars = conn.execute(
            "SELECT COALESCE(SUM(LENGTH(content)), 0) AS total FROM pdf_pages"
        ).fetchone()["total"]

        avg_pages = conn.execute(
            """SELECT COALESCE(ROUND(AVG(pc), 1), 0) AS avg_pages
               FROM (SELECT COUNT(*) AS pc FROM pdf_pages GROUP BY file_id)"""
        ).fetchone()["avg_pages"]

        dirs_rows = conn.execute(
            """SELECT
                 CASE
                   WHEN INSTR(filename, '/') > 0
                   THEN SUBSTR(filename, 1, INSTR(filename, '/') - 1)
                   ELSE '.'
                 END AS dir,
                 COUNT(*) AS cnt
               FROM pdf_files
               GROUP BY dir
               ORDER BY cnt DESC"""
        ).fetchall()
        files_by_dir = {r["dir"]: r["cnt"] for r in dirs_rows}

        return {
            "files": file_count,
            "pages": page_count,
            "total_chars": total_chars,
            "avg_pages_per_file": float(avg_pages),
            "files_by_directory": files_by_dir,
        }
    finally:
        conn.close()
