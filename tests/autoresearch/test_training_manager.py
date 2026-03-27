from __future__ import annotations

import json

from src.autoresearch.training_manager import build_training_manager_review


def test_build_training_manager_review_prioritizes_outliner_after_librarians(tmp_path) -> None:
    repo_root = tmp_path
    (repo_root / "data" / "library" / "reading-notes" / "drafts").mkdir(parents=True)
    (repo_root / "data" / "library").mkdir(parents=True, exist_ok=True)
    (repo_root / "data" / "library" / "resource-catalog.json").write_text(json.dumps([{"title": "Resource A"}]))
    (repo_root / "data" / "library" / "resources" / "one").mkdir(parents=True)
    (repo_root / "data" / "library" / "resources" / "one" / "holding.json").write_text("{}")
    (repo_root / "data" / "library" / "reading-notes" / "drafts" / "resource-a.evaluation.json").write_text("{}")
    (repo_root / "outputs" / "devotionals").mkdir(parents=True)
    (repo_root / "outputs" / "devotionals" / "2026-03-14__034458__proverbs-1-2__12-day__vol-1__meta.json").write_text(
        json.dumps({"run_state": "validated_pass"})
    )
    (repo_root / "outputs" / "devotionals" / "2026-03-14__130313__exodus-19-20__12-day__vol-1__checkpoints").mkdir(parents=True)
    (
        repo_root
        / "outputs"
        / "devotionals"
        / "2026-03-14__130313__exodus-19-20__12-day__vol-1__checkpoints"
        / "028__book-unification.json"
    ).write_text(json.dumps({"payload": {"status": "failed"}}))
    (repo_root / "docs" / "system" / "outputs").mkdir(parents=True, exist_ok=True)
    (repo_root / "docs" / "system" / "outputs" / "2026-03-16__devg__exposition-training-cycle.json").write_text(
        json.dumps(
            {
                "assignments": [{"day_number": 1}],
                "passage_researcher_assignments": [],
                "theological_guidance": {"finding_count": 1},
            }
        )
    )
    (repo_root / "docs" / "system" / "outputs" / "2026-03-16__devg__library-trainer-review.json").write_text(
        json.dumps({"findings": []})
    )
    (repo_root / "docs" / "system" / "outputs" / "2026-03-16__devg__theological-reviewer-report.json").write_text(
        json.dumps({"findings": []})
    )
    (repo_root / "docs" / "system" / "outputs" / "2026-03-16__devg__outliner-training-cycle.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "evaluation": {
                            "status": "fail",
                            "findings": ["Broad or unfocused key verse references appeared 3 time(s)."],
                        }
                    }
                ]
            }
        )
    )

    payload = build_training_manager_review(repo_root)

    assert payload["current_bottleneck_worker"] == "outliner"
    names = [item["worker_name"] for item in payload["reviews"]]
    assert names[:3] == ["acquisition_librarian", "research_librarian", "outliner"]
    assert payload["expert_trainer_inputs"]["exposition_training_cycle_present"] is True
    assert len(payload["expert_trainer_advice"]) >= 4
    outliner_advice = next(item for item in payload["expert_trainer_advice"] if item["trainer_name"] == "expert_outliner_trainer")
    assert outliner_advice["status"] == "consulted"
    exposition = next(item for item in payload["reviews"] if item["worker_name"] == "exposition_writer")
    assert exposition["status"] == "active_training"
    assert "Expert trainer advice:" in exposition["rationale"]
    outliner = next(item for item in payload["reviews"] if item["worker_name"] == "outliner")
    assert any(item.startswith("mentor=expert_outliner_trainer") for item in outliner["evidence"])
