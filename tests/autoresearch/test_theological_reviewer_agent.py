from __future__ import annotations

from pathlib import Path

from src.autoresearch.theological_reviewer_agent import build_theological_reviewer_report


def test_build_theological_reviewer_report_has_profile_and_metrics(tmp_path: Path) -> None:
    repo_root = Path("/Volumes/claude-projects/projects/devotional-generator-system-a")
    payload = build_theological_reviewer_report(repo_root)

    assert payload["trainer_profile"]["role"] == "expert_theological_reviewer"
    assert "junior_worker_assumption" in payload["trainer_profile"]
    assert "book_validation" in payload
    assert "quote_validation" in payload
    assert "findings" in payload
