from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


_DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "library" / "resource-catalog.json"


def _load_catalog_rows_from_db() -> list[dict]:
    """Load resource_catalog rows from SQLite DB. Returns empty list on any error."""
    try:
        from src.persistence.paths import default_registry_db_path
        db_path = default_registry_db_path()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM resource_catalog WHERE catalog_status IN ('verified', 'draft')").fetchall()
        conn.close()
        result = []
        for row in rows:
            r = dict(row)
            for field in ("covered_books", "covered_topics", "supports_workers", "contains", "serves_needs"):
                try:
                    r[field] = json.loads(r.get(field) or "[]")
                except Exception:
                    r[field] = []
            r["approved_for_validator"] = bool(r.get("approved_for_validator"))
            result.append(r)
        return result
    except Exception:
        return []


@dataclass(frozen=True)
class LibraryCatalogEntry:
    resource_id: str
    title: str
    author_or_editor: str
    resource_type: str
    covered_books: tuple[str, ...]
    supports_workers: tuple[str, ...]
    contains: tuple[str, ...]
    serves_needs: tuple[str, ...]
    source_form: str
    source_locator: str
    acquisition_status: str
    catalog_status: str
    preferred_order: int
    notes: str


def load_library_catalog(catalog_path: Path = _DEFAULT_CATALOG_PATH) -> list[LibraryCatalogEntry]:
    # Prefer DB when using the default path; fall back to JSON if DB unavailable
    if catalog_path == _DEFAULT_CATALOG_PATH:
        db_rows = _load_catalog_rows_from_db()
        if db_rows:
            rows = db_rows
        else:
            rows = json.loads(catalog_path.read_text())
    else:
        rows = json.loads(catalog_path.read_text())
    return [
        LibraryCatalogEntry(
            resource_id=str(row.get("resource_id") or "").strip(),
            title=str(row.get("title") or "").strip(),
            author_or_editor=str(row.get("author_or_editor") or "").strip(),
            resource_type=str(row.get("resource_type") or "").strip(),
            covered_books=tuple(str(item).strip() for item in (row.get("covered_books") or []) if str(item).strip()),
            supports_workers=tuple(str(item).strip() for item in (row.get("supports_workers") or []) if str(item).strip()),
            contains=tuple(str(item).strip() for item in (row.get("contains") or []) if str(item).strip()),
            serves_needs=tuple(str(item).strip() for item in (row.get("serves_needs") or []) if str(item).strip()),
            source_form=str(row.get("source_form") or "").strip(),
            source_locator=str(row.get("source_locator") or "").strip(),
            acquisition_status=str(row.get("acquisition_status") or "").strip(),
            catalog_status=str(row.get("catalog_status") or "").strip(),
            preferred_order=int(row.get("preferred_order") or 999),
            notes=str(row.get("notes") or "").strip(),
        )
        for row in rows
    ]


def scripture_book(reference: str) -> str:
    text = " ".join(str(reference or "").split()).strip()
    if not text:
        return ""
    match = re.match(r"^(.+?)\s+\d", text)
    if match:
        return match.group(1).strip()
    return text


def chapter_window(reference: str, *, lookback: int = 1, lookahead: int = 1) -> tuple[int | None, int | None, str]:
    text = " ".join(str(reference or "").split()).strip()
    chapter_numbers = [int(num) for num in re.findall(r"(?<!:)\b(\d+)(?::\d+)?", text)]
    if not chapter_numbers:
        return None, None, ""
    start = min(chapter_numbers)
    end = max(chapter_numbers)
    window_start = max(1, start - max(0, lookback))
    window_end = end + max(0, lookahead)
    return window_start, window_end, f"{window_start}-{window_end}"


def select_catalog_resources(
    *,
    scripture_reference: str,
    worker_name: str,
    requested_needs: list[str],
    catalog_path: Path = _DEFAULT_CATALOG_PATH,
) -> list[LibraryCatalogEntry]:
    book = scripture_book(scripture_reference)
    requested = {str(item).strip() for item in requested_needs if str(item).strip()}
    entries = []
    for entry in load_library_catalog(catalog_path):
        if entry.catalog_status not in {"verified", "draft"}:
            continue
        if entry.acquisition_status not in {"cataloged", "ready", "planned"}:
            continue
        if worker_name and worker_name not in entry.supports_workers and "research_librarian" not in entry.supports_workers:
            continue
        if entry.covered_books and book and book not in entry.covered_books:
            continue
        if requested and not (requested & set(entry.serves_needs)):
            continue
        entries.append(entry)
    return sorted(entries, key=lambda item: (item.preferred_order, item.title.lower()))
