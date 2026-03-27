"""passage_researcher_training_agent.py — Passage researcher proactive drill orchestrator.

The passage researcher's job is to build passage-specific resource bundles for
the exposition writer. Without proactive drills, its training is entirely passive —
it only gets assignments when the exposition cycle finds thin resources.

This agent proactively runs the passage researcher on benchmark passages to:
  1. Surface thin-bundle passages before the exposition writer hits them.
  2. Give the acquisition librarian concrete targets to fill.
  3. Score bundle coverage so the training manager can track improvement.

Scoring is deterministic (resource counts), not LLM-evaluated. The quality
gate is: exposition_resources >= 4 = strong, < 4 = thin (needs work).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.autoresearch.store import log_experiment
from src.persistence.paths import default_registry_db_path
from src.rag.research_librarian import prepare_passage_resource_bundle


# Benchmark passages — diverse genres and book families, deliberately chosen to
# stress-test resource coverage across the library.
_BENCHMARK_PASSAGES = [
    ("Luke 15:11-24", "The prodigal son — narrative/parable, mercy theology"),
    ("Habakkuk 1:1-7", "Habakkuk — prophetic lament, theodicy"),
    ("Colossians 3:1-17", "Colossians — epistle, union with Christ"),
    ("Exodus 20:1-17", "Exodus — law/covenant, Sinai"),
    ("Isaiah 40:28-31", "Isaiah 40 — prophetic encouragement, strength renewed"),
    ("Proverbs 1:1-9", "Proverbs — wisdom literature, fear of the Lord"),
    ("Romans 5:1-11", "Romans — epistle, justification and peace"),
    ("John 10:11-18", "John — gospel discourse, good shepherd"),
    ("Acts 9:1-20", "Acts — narrative, Paul's conversion"),
    ("Ezekiel 37:1-14", "Ezekiel — prophetic vision, dry bones"),
]

_STRONG_THRESHOLD = 4  # exposition_resources >= this = strong


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class PassageResearcherDrillResult:
    passage_reference: str
    description: str
    exposition_resource_count: int
    shared_resource_count: int
    outliner_resource_count: int
    strength: str  # "strong" | "thin"
    rationale: str


def run_passage_researcher_drills(repo_root: Path) -> list[PassageResearcherDrillResult]:
    """Run the passage researcher on all benchmark passages and score bundle coverage."""
    db_path = default_registry_db_path()
    results: list[PassageResearcherDrillResult] = []

    for passage_reference, description in _BENCHMARK_PASSAGES:
        try:
            bundle = prepare_passage_resource_bundle(
                topic=passage_reference,
                scripture_reference=passage_reference,
                db_path=db_path,
            )
        except Exception as exc:
            results.append(
                PassageResearcherDrillResult(
                    passage_reference=passage_reference,
                    description=description,
                    exposition_resource_count=0,
                    shared_resource_count=0,
                    outliner_resource_count=0,
                    strength="thin",
                    rationale=f"Bundle preparation failed: {exc}",
                )
            )
            continue

        expo_count = len(bundle.exposition_resources or [])
        shared_count = len(bundle.shared_resources or [])
        outliner_count = len(bundle.outliner_resources or [])
        strength = "strong" if expo_count >= _STRONG_THRESHOLD else "thin"
        rationale = (
            f"Bundle has {expo_count} exposition resource(s), {shared_count} shared, "
            f"{outliner_count} outliner. "
            + (
                "Adequate for exposition training."
                if strength == "strong"
                else f"Thin — needs at least {_STRONG_THRESHOLD} exposition resources before exposition training is reliable."
            )
        )
        results.append(
            PassageResearcherDrillResult(
                passage_reference=passage_reference,
                description=description,
                exposition_resource_count=expo_count,
                shared_resource_count=shared_count,
                outliner_resource_count=outliner_count,
                strength=strength,
                rationale=rationale,
            )
        )

    return results


def build_passage_researcher_training_cycle(repo_root: Path) -> dict[str, Any]:
    """Build a full passage researcher training cycle report."""
    now = _utc_now()
    drill_results = run_passage_researcher_drills(repo_root)

    strong = [r for r in drill_results if r.strength == "strong"]
    thin = [r for r in drill_results if r.strength == "thin"]

    overall_status = "pass" if len(thin) == 0 else ("revise" if len(strong) >= len(thin) else "fail")

    return {
        "generated_at_utc": now,
        "status": overall_status,
        "summary": (
            f"Passage researcher drilled {len(drill_results)} benchmark passages: "
            f"{len(strong)} strong, {len(thin)} thin."
        ),
        "strong_count": len(strong),
        "thin_count": len(thin),
        "drill_results": [asdict(r) for r in drill_results],
        "acquisition_targets": [
            {
                "passage_reference": r.passage_reference,
                "description": r.description,
                "exposition_resource_count": r.exposition_resource_count,
                "gap": _STRONG_THRESHOLD - r.exposition_resource_count,
            }
            for r in thin
        ],
    }


def log_passage_researcher_training_cycle(repo_root: Path) -> dict[str, Any]:
    payload = build_passage_researcher_training_cycle(repo_root)
    now = _utc_now()

    for result in payload["drill_results"]:
        slug = re.sub(r"[^a-z0-9]+", "-", result["passage_reference"].lower()).strip("-")
        log_experiment(
            experiment_id=f"passage-researcher-drill__{slug}__{now}",
            worker_name="passage_researcher",
            benchmark_name="proactive-bundle-drill",
            benchmark_reference=slug,
            status="pass" if result["strength"] == "strong" else "fail",
            attempted_change=(
                f"Proactive drill: built passage resource bundle for {result['passage_reference']}. "
                f"Strength: {result['strength']}."
            ),
            metrics={
                "exposition_resource_count": result["exposition_resource_count"],
                "shared_resource_count": result["shared_resource_count"],
                "outliner_resource_count": result["outliner_resource_count"],
            },
            learning_note=(
                "Proactive passage researcher drill — surfaces thin bundles before the exposition writer hits them. "
                f"Threshold: {_STRONG_THRESHOLD} exposition resources = strong."
            ),
            keep_decision="keep" if result["strength"] == "strong" else "review",
            created_at_utc=now,
            completed_at_utc=now,
        )

    # Summary experiment for the training manager to read
    log_experiment(
        experiment_id=f"passage-researcher-cycle-review__{now}",
        worker_name="passage_researcher",
        benchmark_name="proactive-bundle-cycle-review",
        benchmark_reference="benchmark-passages",
        status=payload["status"],
        attempted_change=(
            f"Passage researcher proactive drill cycle: {payload['strong_count']} strong, "
            f"{payload['thin_count']} thin across {len(payload['drill_results'])} benchmark passages."
        ),
        metrics={
            "strong_count": payload["strong_count"],
            "thin_count": payload["thin_count"],
            "total_drilled": len(payload["drill_results"]),
        },
        learning_note=(
            "Pass = all benchmark bundles strong. Revise = more strong than thin. Fail = more thin than strong. "
            "Thin passages become acquisition_targets for the library to fill."
        ),
        keep_decision="keep" if payload["status"] == "pass" else "review",
        created_at_utc=now,
        completed_at_utc=now,
    )

    return payload
