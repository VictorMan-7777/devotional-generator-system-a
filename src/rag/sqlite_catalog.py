from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from src.citations.quote_citations import normalize_quote_citation_fields


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _load_quote_seed_rows(seed_path: Path) -> list[dict[str, Any]]:
    raw = json.loads(seed_path.read_text(encoding="utf-8"))
    return [normalize_quote_citation_fields(r) for r in raw]


def _load_excerpt_seed_rows(seed_path: Path) -> list[dict[str, Any]]:
    raw = json.loads(seed_path.read_text(encoding="utf-8"))
    return [
        {
            "text": str(r.get("text", "")).strip(),
            "source_title": str(r.get("source_title", "")).strip(),
            "author": str(r.get("author", "")).strip(),
            "source_type": str(r.get("source_type", "")).strip(),
            "paragraph_type": str(r.get("paragraph_type", "")).strip(),
        }
        for r in raw
    ]


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        conn.commit()


def load_quote_rows(db_path: Path, seed_path: Path, *, strict_db_only: bool = False) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quote_catalog (
              quote_text TEXT NOT NULL,
              author TEXT NOT NULL,
              source_title TEXT NOT NULL,
              publication_year INTEGER NOT NULL,
              page_or_url TEXT NOT NULL,
              citation_locator TEXT NOT NULL DEFAULT '',
              source_url TEXT NOT NULL DEFAULT '',
              publisher TEXT NOT NULL DEFAULT '',
              publication_city TEXT NOT NULL DEFAULT '',
              public_domain INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        _ensure_column(conn, "quote_catalog", "citation_locator", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "quote_catalog", "source_url", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "quote_catalog", "publisher", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "quote_catalog", "publication_city", "TEXT NOT NULL DEFAULT ''")
        existing_rows = conn.execute(
            """
            SELECT
              rowid, quote_text, author, source_title, publication_year, page_or_url,
              citation_locator, source_url, publisher, publication_city, public_domain
            FROM quote_catalog
            """
        ).fetchall()
        for row in existing_rows:
            normalized = normalize_quote_citation_fields(dict(row))
            conn.execute(
                """
                UPDATE quote_catalog
                SET citation_locator = ?, source_url = ?, publisher = ?, publication_city = ?
                WHERE rowid = ?
                """,
                (
                    normalized.get("citation_locator", ""),
                    normalized.get("source_url", ""),
                    normalized.get("publisher", ""),
                    normalized.get("publication_city", ""),
                    row["rowid"],
                ),
            )
        conn.commit()
        count = int(conn.execute("SELECT COUNT(*) FROM quote_catalog").fetchone()[0])
        if count == 0:
            if strict_db_only:
                raise ValueError(
                    "quote_catalog table is empty in DB-first mode. "
                    "Bootstrap catalog explicitly before generation."
                )
            raw = json.loads(seed_path.read_text(encoding="utf-8"))
            conn.executemany(
                """
                INSERT INTO quote_catalog
                  (
                    quote_text, author, source_title, publication_year, page_or_url,
                    citation_locator, source_url, publisher, publication_city, public_domain
                  )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        normalized.get("quote_text", ""),
                        normalized.get("author", ""),
                        normalized.get("source_title", ""),
                        int(normalized.get("publication_year", 0)),
                        normalized.get("page_or_url", ""),
                        normalized.get("citation_locator", ""),
                        normalized.get("source_url", ""),
                        normalized.get("publisher", ""),
                        normalized.get("publication_city", ""),
                        1 if bool(normalized.get("public_domain", True)) else 0,
                    )
                    for normalized in (
                        normalize_quote_citation_fields(r)
                        for r in raw
                    )
                ],
            )
            conn.commit()
            rows = conn.execute(
                """
                SELECT
                  quote_text, author, source_title, publication_year, page_or_url,
                  citation_locator, source_url, publisher, publication_city, public_domain
                FROM quote_catalog
                """
            ).fetchall()
            return [normalize_quote_citation_fields(dict(r)) for r in rows]
        rows = conn.execute(
            """
            SELECT
              quote_text, author, source_title, publication_year, page_or_url,
              citation_locator, source_url, publisher, publication_city, public_domain
            FROM quote_catalog
            """
        ).fetchall()
        return [normalize_quote_citation_fields(dict(r)) for r in rows]
    except sqlite3.OperationalError:
        if strict_db_only:
            raise
        return _load_quote_seed_rows(seed_path)
    finally:
        conn.close()


def load_excerpt_rows(db_path: Path, seed_path: Path, *, strict_db_only: bool = False) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS excerpt_catalog (
              text TEXT NOT NULL,
              source_title TEXT NOT NULL,
              author TEXT NOT NULL,
              source_type TEXT NOT NULL,
              paragraph_type TEXT NOT NULL,
              passage_reference TEXT NOT NULL DEFAULT ''
            )
            """
        )
        # Migrate existing rows: add passage_reference column if absent.
        _ensure_column(conn, "excerpt_catalog", "passage_reference", "TEXT NOT NULL DEFAULT ''")
        count = int(conn.execute("SELECT COUNT(*) FROM excerpt_catalog").fetchone()[0])
        if count == 0:
            if strict_db_only:
                raise ValueError(
                    "excerpt_catalog table is empty in DB-first mode. "
                    "Bootstrap catalog explicitly before generation."
                )
            raw = json.loads(seed_path.read_text(encoding="utf-8"))
            conn.executemany(
                """
                INSERT INTO excerpt_catalog
                  (text, source_title, author, source_type, paragraph_type, passage_reference)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(r.get("text", "")).strip(),
                        str(r.get("source_title", "")).strip(),
                        str(r.get("author", "")).strip(),
                        str(r.get("source_type", "")).strip(),
                        str(r.get("paragraph_type", "")).strip(),
                        str(r.get("passage_reference", "")).strip(),
                    )
                    for r in raw
                ],
            )
            conn.commit()
        rows = conn.execute(
            """
            SELECT text, source_title, author, source_type, paragraph_type, passage_reference
            FROM excerpt_catalog
            """
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        if strict_db_only:
            raise
        return _load_excerpt_seed_rows(seed_path)
    finally:
        conn.close()


def bootstrap_catalog_tables(*, db_path: Path, quote_seed_path: Path, excerpt_seed_path: Path) -> None:
    """Ensure local quote/excerpt catalog tables are populated for DB-first runs."""
    load_quote_rows(db_path=db_path, seed_path=quote_seed_path, strict_db_only=False)
    load_excerpt_rows(db_path=db_path, seed_path=excerpt_seed_path, strict_db_only=False)
