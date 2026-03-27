from __future__ import annotations

from pathlib import Path

from src.autoresearch.action_writer_training_agent import build_action_writer_training_cycle


def test_build_action_writer_training_cycle_returns_status() -> None:
    repo_root = Path("/Volumes/claude-projects/projects/devotional-generator-system-a")
    payload = build_action_writer_training_cycle(repo_root)

    assert payload["status"] in {"ready", "blocked"}
    if payload["status"] == "ready":
        assert payload["assignments"]
        first = payload["assignments"][0]
        assert first["focal_reference"]
        assert first["context_reference"]
        assert first["item_count"] >= 0
        assert "connector_phrase" in first


def test_build_action_writer_training_cycle_blocked_without_artifact(tmp_path) -> None:
    payload = build_action_writer_training_cycle(tmp_path)
    assert payload["status"] == "blocked"
    assert "summary" in payload
    assert payload["assignments"] == []
