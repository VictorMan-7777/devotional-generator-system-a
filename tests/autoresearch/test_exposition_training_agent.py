from __future__ import annotations

from pathlib import Path

from src.autoresearch.exposition_training_agent import build_exposition_training_cycle


def test_build_exposition_training_cycle_returns_assignments() -> None:
    repo_root = Path("/Volumes/claude-projects/projects/devotional-generator-system-a")
    payload = build_exposition_training_cycle(repo_root)

    assert payload["status"] in {"ready", "blocked"}
    if payload["status"] == "ready":
        assert payload["assignments"]
        first = payload["assignments"][0]
        assert first["focal_reference"]
        assert first["context_reference"]
