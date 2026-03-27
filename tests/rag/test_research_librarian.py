from __future__ import annotations

from pathlib import Path

import pytest

from src.rag.research_librarian import (
    apply_library_trainer_review,
    prepare_passage_resource_bundle,
)
from src.rag.research_memory import _connect, _ensure_schema


def test_prepare_passage_resource_bundle_uses_outline_memory(tmp_path: Path) -> None:
    db_path = tmp_path / "library.db"
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO outline_research_memory (
              outline_key, day_number, week_number, passage_reference, focus_label,
              source_kind, source_title, notes, selected_count, last_selected_for_reference
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "luke-15-outline",
                1,
                1,
                "Luke 15",
                "Joy over the found",
                "commentary-outline",
                "Luke Commentary",
                "Movement from complaint to celebration.",
                2,
                "Luke 15",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    bundle = prepare_passage_resource_bundle(
        topic="Luke 15",
        scripture_reference="Luke 15",
        db_path=db_path,
    )

    assert bundle.scripture_reference == "Luke 15"
    assert bundle.outliner_resources
    assert bundle.outliner_resources[0].source_title == "Luke Commentary"
    assert bundle.outliner_resources[0].excerpt_text == "Joy over the found"


def test_prepare_passage_resource_bundle_requests_acquisition_when_thin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []

    def fake_request(**kwargs):
        calls.append(kwargs)
        return kwargs

    monkeypatch.setattr(
        "src.rag.research_librarian.request_resource_acquisition",
        fake_request,
    )
    monkeypatch.setattr(
        "src.rag.research_librarian.ExpositionRAG.retrieve_for_paragraph",
        lambda self, paragraph_type, passage_reference, topic, source_types: [],
    )

    bundle = prepare_passage_resource_bundle(
        topic="Zephaniah 1-3",
        scripture_reference="Zephaniah 1-3",
        db_path=tmp_path / "thin.db",
    )

    assert bundle.scripture_reference == "Zephaniah 1-3"
    assert calls
    assert calls[0]["requested_by"] == "research_librarian"
    assert calls[0]["status"] == "trainer_review"
    assert "exposition" in calls[0]["requested_resource_kinds"] or "outline" in calls[0]["requested_resource_kinds"]


def test_prepare_passage_resource_bundle_adds_catalog_outline_help(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.rag.research_librarian.ExpositionRAG.retrieve_for_paragraph",
        lambda self, paragraph_type, passage_reference, topic, source_types: [],
    )
    monkeypatch.setattr(
        "src.rag.research_librarian.request_resource_acquisition",
        lambda **kwargs: kwargs,
    )
    monkeypatch.setattr(
        "src.rag.research_librarian.select_catalog_resources",
        lambda scripture_reference, worker_name, requested_needs: [
            type(
                "Entry",
                (),
                {
                    "title": "The Pulpit Commentary: Ephesians",
                    "author_or_editor": "H. D. M. Spence and Joseph Exell",
                    "resource_type": "book_commentary",
                    "contains": ("section_outlines", "table_of_contents_outline"),
                    "notes": "Test card",
                    "preferred_order": 10,
                },
            )()
        ],
    )
    bundle = prepare_passage_resource_bundle(
        topic="Ephesians 4-6",
        scripture_reference="Ephesians 4-6",
        db_path=Path("/tmp/devg-library-test.db"),
    )

    titles = {entry.source_title for entry in bundle.outliner_resources}
    assert "The Pulpit Commentary: Ephesians" in titles
    target = next(entry for entry in bundle.outliner_resources if entry.source_title == "The Pulpit Commentary: Ephesians")
    assert "chapters 3-7" in target.note
    assert "section_outlines" in target.excerpt_text


def test_clear_requests_satisfied_by_current_holdings(monkeypatch: pytest.MonkeyPatch) -> None:
    updated: list[dict[str, object]] = []

    monkeypatch.setattr(
        "src.rag.research_librarian.update_resource_acquisition_request",
        lambda **kwargs: updated.append(kwargs) or kwargs,
    )

    from src.rag.research_librarian import clear_requests_satisfied_by_current_holdings

    cleared = clear_requests_satisfied_by_current_holdings(
        [
            {
                "request_id": "req-1",
                "scripture_reference": "Luke 15",
                "matching_current_holdings": 22,
            }
        ]
    )

    assert cleared == ["req-1"]
    assert updated[0]["status"] == "answered"
    assert "Luke 15" in str(updated[0]["notes"])


def test_apply_library_trainer_review_can_approve_acquisition_librarian(monkeypatch: pytest.MonkeyPatch) -> None:
    updated: list[dict[str, object]] = []

    monkeypatch.setattr(
        "src.rag.research_librarian.update_resource_acquisition_request",
        lambda **kwargs: updated.append(kwargs) or kwargs,
    )

    result = apply_library_trainer_review(
        [
            {
                "request_id": "req-2",
                "scripture_reference": "Habakkuk 1-3",
                "matching_current_holdings": 1,
                "recommended_resolution": "approve_for_acquisition_librarian",
            }
        ]
    )

    assert result["approved_request_ids"] == ["req-2"]
    assert updated[0]["status"] == "requested"
