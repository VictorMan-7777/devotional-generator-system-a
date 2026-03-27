from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.rag.cuttings_inventory import inventory_cutting_sources, synchronize_cuttings_with_library


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_cycle() -> dict[str, object]:
    synchronize_cuttings_with_library()
    items = inventory_cutting_sources()
    unique: list[dict[str, object]] = []
    seen_titles: set[str] = set()
    for item in items:
        if item.source_title in seen_titles:
            continue
        seen_titles.add(item.source_title)
        unique.append(
            {
                "source_title": item.source_title,
                "author": item.author,
                "source_kind": item.source_kind,
                "cutting_count": item.cutting_count,
            }
        )
        if len(unique) >= 2:
            break

    assignments = []
    owners = ["acquisition_librarian", "research_librarian"]
    for owner, source in zip(owners, unique):
        assignments.append(
            {
                "owner": owner,
                "resource_title": source["source_title"],
                "author": source["author"],
                "source_kind": source["source_kind"],
                "cutting_count": source["cutting_count"],
                "task": "Acquire the parent resource, then collaborate on a draft card for evaluation.",
            }
        )

    return {
        "cycle_name": "library_bootstrap_cycle_1",
        "created_at_utc": _utc_stamp(),
        "assignments": assignments,
        "evaluation_rubric_path": "docs/system/library-card-evaluation-rubric.md",
        "live_catalog_path": "data/library/resource-catalog.json",
        "example_catalog_path": "data/library/resource-catalog.examples.json",
    }


def main() -> int:
    print(json.dumps(build_cycle(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
