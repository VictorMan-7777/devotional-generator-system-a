from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_QUOTE_SEED = Path(__file__).resolve().parents[2] / "data" / "quotes" / "seed-quotes.json"
_DEFAULT_EXCERPT_SEED = Path(__file__).resolve().parents[2] / "data" / "excerpts" / "seed-excerpts.json"


@dataclass(frozen=True)
class CuttingSource:
    source_title: str
    author: str
    source_kind: str
    cutting_count: int

def _load_rows(path: Path) -> list[dict[str, object]]:
    return list(json.loads(path.read_text()))


def _row_title(row: dict[str, object]) -> str:
    return str(row.get("source_title") or "").strip()


def inventory_cutting_sources(
    quote_seed_path: Path = _DEFAULT_QUOTE_SEED,
    excerpt_seed_path: Path = _DEFAULT_EXCERPT_SEED,
    *,
    retired_titles: set[str] | None = None,
) -> list[CuttingSource]:
    retired = retired_titles or set()
    counter: Counter[tuple[str, str, str]] = Counter()
    for path, source_kind in (
        (quote_seed_path, "quote_cuttings"),
        (excerpt_seed_path, "excerpt_cuttings"),
    ):
        rows = _load_rows(path)
        for row in rows:
            title = str(row.get("source_title") or "").strip()
            author = str(row.get("author") or "").strip()
            if not title or title in retired:
                continue
            counter[(title, author, source_kind)] += 1
    results = [
        CuttingSource(
            source_title=title,
            author=author,
            source_kind=source_kind,
            cutting_count=count,
        )
        for (title, author, source_kind), count in counter.items()
    ]
    return sorted(results, key=lambda item: (-item.cutting_count, item.source_title.lower()))


def inventory_as_jsonable(
    quote_seed_path: Path = _DEFAULT_QUOTE_SEED,
    excerpt_seed_path: Path = _DEFAULT_EXCERPT_SEED,
    *,
    retired_titles: set[str] | None = None,
) -> list[dict[str, object]]:
    return [
        {
            "source_title": item.source_title,
            "author": item.author,
            "source_kind": item.source_kind,
            "cutting_count": item.cutting_count,
        }
        for item in inventory_cutting_sources(
            quote_seed_path,
            excerpt_seed_path,
            retired_titles=retired_titles,
        )
    ]


def retire_accepted_cuttings(
    quote_seed_path: Path = _DEFAULT_QUOTE_SEED,
    excerpt_seed_path: Path = _DEFAULT_EXCERPT_SEED,
    *,
    retired_titles: set[str] | None = None,
) -> dict[str, int]:
    retired = retired_titles or set()
    results: dict[str, int] = {}
    for path in (quote_seed_path, excerpt_seed_path):
        rows = _load_rows(path)
        kept = [row for row in rows if _row_title(row) not in retired]
        removed = len(rows) - len(kept)
        if removed:
            path.write_text(json.dumps(kept, indent=2) + "\n")
        results[str(path)] = removed
    results["total_removed"] = sum(count for key, count in results.items() if key != "total_removed")
    return results


def synchronize_cuttings_with_library() -> dict[str, int]:
    return {"total_removed": 0}
