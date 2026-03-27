from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from src.autoresearch.outliner_training_agent import evaluate_outline_artifact
from src.autoresearch.reasoning_outliner_core import build_reasoning_editorial_artifact
from src.autoresearch.store import record_outliner_system_comparison
from src.generation.editorial import (
    build_editorial_artifact,
    build_editorial_day_brief,
    differentiate_day_briefs,
)
from src.persistence.paths import default_registry_db_path
from src.rag.research_librarian import prepare_passage_resource_bundle
from src.scripture.planner import (
    plan_scripture_day_references,
    select_daily_key_verses_reference,
    suggest_study_window_size,
)
from src.scripture.retrieval import ScriptureFailureAlert, ScriptureRetriever, ScriptureResult


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _scripture_text(retriever: ScriptureRetriever, reference: str) -> str:
    result = retriever.retrieve(reference=reference)
    if isinstance(result, ScriptureResult):
        return result.text
    if isinstance(result, ScriptureFailureAlert):
        return reference
    return reference


def _slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def _day_inputs(
    *,
    scripture_reference: str,
    num_days: int,
    retriever: ScriptureRetriever,
) -> list[dict[str, str]]:
    references = plan_scripture_day_references(
        reference=scripture_reference,
        num_days=num_days,
        max_verses_per_day=suggest_study_window_size(reference=scripture_reference, num_days=num_days),
        retriever=retriever,
    )
    rows: list[dict[str, str]] = []
    for reference in references:
        rows.append(
            {
                "study_window_reference": reference,
                "key_verse_reference": select_daily_key_verses_reference(reference=reference, max_key_verses=2),
                "scripture_reference": select_daily_key_verses_reference(reference=reference, max_key_verses=2),
                "scripture_text": _scripture_text(retriever, reference),
            }
        )
    return rows


def _build_legacy_artifact(
    *,
    scripture_reference: str,
    num_days: int,
    num_weeks: int,
    day_inputs: list[dict[str, str]],
    bundle,
):
    day_briefs = []
    day_plan_rows = []
    for idx, row in enumerate(day_inputs, start=1):
        brief = build_editorial_day_brief(
            day_number=idx,
            scripture_reference=row["scripture_reference"],
            scripture_text=row["scripture_text"],
            study_window_reference=row["study_window_reference"],
            passage_resources=bundle,
        )
        # Keep the week assignment simple and comparable to the redesigned path.
        brief = replace(
            brief,
            week_number=min(num_weeks, max(1, ((idx - 1) * num_weeks) // max(num_days, 1) + 1)),
        )
        day_briefs.append(brief)
        day_plan_rows.append(
            {
                "day_number": str(idx),
                "week_number": str(brief.week_number),
                "topic": scripture_reference,
                "scripture_reference": row["scripture_reference"],
                "study_window_reference": row["study_window_reference"],
            }
        )
    day_briefs = differentiate_day_briefs(day_briefs)
    return build_editorial_artifact(
        topic=scripture_reference,
        num_days=num_days,
        source_reference=scripture_reference,
        day_plan_rows=day_plan_rows,
        day_briefs=day_briefs,
        passage_resources=bundle,
    )


def compare_outliner_systems(
    *,
    scripture_reference: str,
    passage_slug: str,
    num_days: int,
    num_weeks: int,
    reviewed_by: str = "training_manager",
) -> dict[str, Any]:
    created_at = _utc_now()
    retriever = ScriptureRetriever()
    bundle = prepare_passage_resource_bundle(
        topic=scripture_reference,
        scripture_reference=scripture_reference,
        db_path=default_registry_db_path(),
    )
    day_inputs = _day_inputs(
        scripture_reference=scripture_reference,
        num_days=num_days,
        retriever=retriever,
    )

    legacy_artifact = _build_legacy_artifact(
        scripture_reference=scripture_reference,
        num_days=num_days,
        num_weeks=num_weeks,
        day_inputs=day_inputs,
        bundle=bundle,
    )
    redesigned_artifact = build_reasoning_editorial_artifact(
        topic=scripture_reference,
        source_reference=scripture_reference,
        num_days=num_days,
        num_weeks=num_weeks,
        day_inputs=day_inputs,
        passage_resources=bundle,
    )

    legacy_eval = evaluate_outline_artifact(legacy_artifact)
    redesigned_eval = evaluate_outline_artifact(redesigned_artifact)

    legacy_score = float(legacy_eval["score"])
    redesigned_score = float(redesigned_eval["score"])
    winner = ""
    if redesigned_score > legacy_score:
        winner = "redesigned"
    elif legacy_score > redesigned_score:
        winner = "legacy"
    else:
        winner = "tie"

    record = record_outliner_system_comparison(
        comparison_id=f"cmp__outliner__{passage_slug}__{num_days}d_{num_weeks}w",
        scripture_reference=scripture_reference,
        passage_slug=passage_slug,
        range_label=f"{num_days}d_{num_weeks}w",
        assignment_payload={
            "scripture_reference": scripture_reference,
            "passage_slug": passage_slug,
            "num_days": num_days,
            "num_weeks": num_weeks,
        },
        interaction_log={
            "comparison_mode": "scored_side_by_side",
            "day_inputs": day_inputs,
        },
        packet_snapshot={
            "shared_resources": len(bundle.shared_resources),
            "outliner_resources": len(bundle.outliner_resources),
            "exposition_resources": len(bundle.exposition_resources),
        },
        reviewer_guidance={
            "legacy_findings": legacy_eval.get("findings", []),
            "redesigned_findings": redesigned_eval.get("findings", []),
        },
        artifact_paths={
            "legacy_production_core": "/Volumes/claude-projects/projects/devotional-generator-system-a/src/generation/editorial.py",
            "legacy_lookup_core": "/Volumes/claude-projects/projects/devotional-generator-system-a/src/generation/outliner_resources.py",
            "redesigned_core": "/Volumes/claude-projects/projects/devotional-generator-system-a/src/autoresearch/reasoning_outliner_core.py",
        },
        legacy_system_name="deterministic_editorial",
        legacy_system_reference="src/generation/editorial.py + src/generation/outliner_resources.py",
        legacy_status=str(legacy_eval["status"]),
        legacy_score=legacy_score,
        legacy_summary="Legacy production core using cue-driven editorial helper path.",
        legacy_metrics=legacy_eval,
        redesigned_system_name="reasoning_outliner_candidate",
        redesigned_system_reference="src/autoresearch/reasoning_outliner_core.py",
        redesigned_status=str(redesigned_eval["status"]),
        redesigned_score=redesigned_score,
        redesigned_summary="Independent reasoning outliner core without legacy cue tables or post-hoc differentiation.",
        redesigned_metrics=redesigned_eval,
        winner=winner,
        decision_status="scored",
        decision_rationale=(
            f"Legacy score={legacy_score:.1f}, redesigned score={redesigned_score:.1f}. "
            f"Winner={winner}."
        ),
        comparison_notes="First fair scored comparison using an independent reasoning core for the redesigned path.",
        reviewed_by=reviewed_by,
        created_at_utc=created_at,
        completed_at_utc=created_at,
    )
    return {
        "record": record.model_dump(mode="json"),
        "legacy_evaluation": legacy_eval,
        "redesigned_evaluation": redesigned_eval,
        "legacy_artifact": legacy_artifact.model_dump(mode="json"),
        "redesigned_artifact": redesigned_artifact.model_dump(mode="json"),
        "shared_bundle_counts": {
            "shared": len(bundle.shared_resources),
            "outliner": len(bundle.outliner_resources),
            "exposition": len(bundle.exposition_resources),
        },
    }


def default_passage_slug(reference: str) -> str:
    return _slugify(reference)
