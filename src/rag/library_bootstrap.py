from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.rag.cuttings_inventory import inventory_cutting_sources, synchronize_cuttings_with_library
from src.rag.library_catalog import load_library_catalog


@dataclass(frozen=True)
class LibraryBootstrapItem:
    source_title: str
    author: str
    source_kind: str
    cutting_count: int
    live_catalog_status: str
    next_step: str
    reading_notes_status: str = "not_started"


def build_library_bootstrap_backlog(
    catalog_path: Path | None = None,
) -> list[LibraryBootstrapItem]:
    synchronize_cuttings_with_library()
    catalog = load_library_catalog(catalog_path) if catalog_path else load_library_catalog()
    by_title = {entry.title: entry for entry in catalog}
    items: list[LibraryBootstrapItem] = []
    for source in inventory_cutting_sources():
        entry = by_title.get(source.source_title)
        if entry is None:
            live_catalog_status = "missing"
            next_step = "acquire_parent_resource"
            reading_notes_status = "blocked_until_live_card"
        elif entry.catalog_status != "verified":
            live_catalog_status = entry.catalog_status
            next_step = "evaluate_or_recreate_card"
            reading_notes_status = "blocked_until_live_card"
        else:
            live_catalog_status = "verified"
            next_step = "available_for_research_librarian"
            reading_notes_status = "ready_for_notes_and_review"
        items.append(
            LibraryBootstrapItem(
                source_title=source.source_title,
                author=source.author,
                source_kind=source.source_kind,
                cutting_count=source.cutting_count,
                live_catalog_status=live_catalog_status,
                next_step=next_step,
                reading_notes_status=reading_notes_status,
            )
        )
    return items


def bootstrap_summary(
    catalog_path: Path | None = None,
) -> dict[str, object]:
    items = build_library_bootstrap_backlog(catalog_path)
    total = len(items)
    available = sum(1 for item in items if item.next_step == "available_for_research_librarian")
    pending = total - available
    return {
        "total_cutting_sources": total,
        "available_for_research_librarian": available,
        "remaining_training_backlog": pending,
        "complete": pending == 0,
        "items": [
            {
                "source_title": item.source_title,
                "author": item.author,
                "source_kind": item.source_kind,
                "cutting_count": item.cutting_count,
                "live_catalog_status": item.live_catalog_status,
                "next_step": item.next_step,
                "reading_notes_status": item.reading_notes_status,
            }
            for item in items
        ],
    }


def bootstrap_summary_json(catalog_path: Path | None = None) -> str:
    return json.dumps(bootstrap_summary(catalog_path), indent=2)
