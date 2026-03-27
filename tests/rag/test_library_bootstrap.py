from __future__ import annotations

from src.rag.library_bootstrap import bootstrap_summary


def test_bootstrap_summary_tracks_remaining_backlog() -> None:
    summary = bootstrap_summary()
    assert summary["total_cutting_sources"] >= 1
    assert summary["remaining_training_backlog"] >= 1
    assert summary["complete"] is False
    assert "reading_notes_status" in summary["items"][0]
    assert summary["items"][0]["reading_notes_status"] in {
        "blocked_until_live_card",
        "ready_for_notes_and_review",
    }
