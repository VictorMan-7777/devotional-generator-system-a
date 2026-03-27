from __future__ import annotations

import json

from src.rag.library_catalog import chapter_window, select_catalog_resources


def test_chapter_window_expands_reference_context() -> None:
    start, end, label = chapter_window("Ephesians 4-6")
    assert start == 3
    assert end == 7
    assert label == "3-7"


def test_select_catalog_resources_for_outliner_uses_catalog_metadata(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(
        json.dumps(
            [
                {
                    "resource_id": "res-book-ephesians-test",
                    "title": "The Pulpit Commentary: Ephesians",
                    "author_or_editor": "H. D. M. Spence and Joseph S. Exell",
                    "resource_type": "book_commentary",
                    "covered_books": ["Ephesians"],
                    "supports_workers": ["research_librarian", "outliner"],
                    "contains": ["section_outlines", "table_of_contents_outline", "verse_commentary"],
                    "serves_needs": ["outline", "structure", "exposition"],
                    "source_form": "url",
                    "source_locator": "catalog-known",
                    "acquisition_status": "cataloged",
                    "catalog_status": "verified",
                    "preferred_order": 10,
                    "notes": "Test catalog entry",
                }
            ]
        )
    )
    entries = select_catalog_resources(
        scripture_reference="Ephesians 4-6",
        worker_name="outliner",
        requested_needs=["outline", "structure"],
        catalog_path=catalog_path,
    )
    titles = {entry.title for entry in entries}
    assert "The Pulpit Commentary: Ephesians" in titles
    target = next(entry for entry in entries if entry.title == "The Pulpit Commentary: Ephesians")
    assert "section_outlines" in target.contains
    assert "table_of_contents_outline" in target.contains
