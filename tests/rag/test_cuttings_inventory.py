from __future__ import annotations

import json

from src.rag.cuttings_inventory import inventory_cutting_sources, retire_accepted_cuttings


def test_inventory_cutting_sources_excludes_retired_parent_titles(tmp_path) -> None:
    quote_seed = tmp_path / "quotes.json"
    excerpt_seed = tmp_path / "excerpts.json"
    quote_seed.write_text(
        json.dumps(
            [
                {"source_title": "Accepted Book", "author": "Author A"},
                {"source_title": "Still Cutting", "author": "Author B"},
            ]
        )
    )
    excerpt_seed.write_text(
        json.dumps(
            [
                {"source_title": "Accepted Book", "author": "Author A"},
                {"source_title": "Still Cutting", "author": "Author B"},
            ]
        )
    )

    items = inventory_cutting_sources(
        quote_seed,
        excerpt_seed,
        retired_titles={"Accepted Book"},
    )

    titles = {item.source_title for item in items}
    assert "Accepted Book" not in titles
    assert "Still Cutting" in titles


def test_retire_accepted_cuttings_removes_rows_from_seed_files(tmp_path) -> None:
    quote_seed = tmp_path / "quotes.json"
    excerpt_seed = tmp_path / "excerpts.json"
    quote_seed.write_text(
        json.dumps(
            [
                {"source_title": "Accepted Book", "author": "Author A"},
                {"source_title": "Still Cutting", "author": "Author B"},
            ]
        )
    )
    excerpt_seed.write_text(
        json.dumps(
            [
                {"source_title": "Accepted Book", "author": "Author A"},
                {"source_title": "Different Book", "author": "Author C"},
            ]
        )
    )

    result = retire_accepted_cuttings(
        quote_seed,
        excerpt_seed,
        retired_titles={"Accepted Book"},
    )

    assert result["total_removed"] == 2
    assert json.loads(quote_seed.read_text()) == [{"source_title": "Still Cutting", "author": "Author B"}]
    assert json.loads(excerpt_seed.read_text()) == [{"source_title": "Different Book", "author": "Author C"}]
