"""outliner_adapter.py — Routes outline artifact generation to reasoning or legacy path.

Default mode is "reasoning" — deterministic key-term-anchored templates.
The outliner is a pipeline worker trained by the LLM outliner trainer, not an LLM agent itself.

Set DEVG_OUTLINER_MODE=legacy for the original deterministic PassageCue path (comparison only).
Set DEVG_OUTLINER_MODE=llm to run the LLM outliner for comparison baseline purposes only —
this is NOT the training path and should not be used in normal training cycles.
Set DEVG_OUTLINER_MODE=argumentative to force argumentative mode for any passage.

Hebrews passages (source_reference starting with "Hebrews") are automatically routed to
the argumentative outliner regardless of DEVG_OUTLINER_MODE — no env var needed.
"""
from __future__ import annotations

import os

from src.autoresearch.reasoning_outliner_core import build_reasoning_editorial_artifact
from src.models.pipeline import EditorialBuildArtifact, PassageResourceBundle


def outliner_mode() -> str:
    """Return the active outliner mode.

    "reasoning"      — deterministic key-term-anchored templates (default, pipeline worker mode)
    "legacy"         — original deterministic PassageCue lookup path (comparison baseline only)
    "llm"            — LLM generates the outline (comparison baseline only, not the training path)
    "argumentative"  — cumulative-argument LLM outliner for Hebrews-style epistles (Stage 1)
    """
    return os.environ.get("DEVG_OUTLINER_MODE", "reasoning").strip().lower()


def build_outline_artifact(
    *,
    topic: str,
    source_reference: str,
    num_days: int,
    num_weeks: int,
    day_inputs: list[dict[str, str]],
    passage_resources: PassageResourceBundle | None = None,
) -> EditorialBuildArtifact:
    """Build an outline artifact using the active outliner path.

    day_inputs is a list of per-day dicts, each with:
        scripture_reference   — narrow key verse reference
        study_window_reference — broader daily study window
        key_verse_reference   — specific focal verse(s)
        scripture_text        — raw scripture text for the study window

    Returns EditorialBuildArtifact in the same shape regardless of mode.
    """
    mode = outliner_mode()

    # Hebrews auto-detection (C7 — deterministic map, no scope creep) or explicit mode flag
    if mode == "argumentative" or source_reference.lower().startswith("hebrews"):
        from src.autoresearch.argumentative_outliner import build_argumentative_outline_artifact
        return build_argumentative_outline_artifact(
            topic=topic,
            source_reference=source_reference,
            num_days=num_days,
            num_weeks=num_weeks,
            day_inputs=day_inputs,
            passage_resources=passage_resources,
        )

    if mode == "legacy":
        return _build_legacy_artifact(
            topic=topic,
            source_reference=source_reference,
            num_days=num_days,
            num_weeks=num_weeks,
            day_inputs=day_inputs,
            passage_resources=passage_resources,
        )
    if mode == "reasoning":
        return build_reasoning_editorial_artifact(
            topic=topic,
            source_reference=source_reference,
            num_days=num_days,
            num_weeks=num_weeks,
            day_inputs=day_inputs,
            passage_resources=passage_resources,
        )
    # llm mode: comparison baseline only — not the normal training path
    from src.autoresearch.llm_outliner_core import build_llm_editorial_artifact
    return build_llm_editorial_artifact(
        topic=topic,
        source_reference=source_reference,
        num_days=num_days,
        num_weeks=num_weeks,
        day_inputs=day_inputs,
        passage_resources=passage_resources,
    )


def _build_legacy_artifact(
    *,
    topic: str,
    source_reference: str,
    num_days: int,
    num_weeks: int,
    day_inputs: list[dict[str, str]],
    passage_resources: PassageResourceBundle | None = None,
) -> EditorialBuildArtifact:
    """Legacy path — deterministic editorial cue engine.

    Kept available for comparison and fallback during migration.
    Not the primary path once adapter is in place.
    """
    from dataclasses import replace

    from src.autoresearch.reasoning_outliner_core import reasoning_week_number
    from src.generation.editorial import (
        build_editorial_artifact,
        build_editorial_day_brief,
        differentiate_day_briefs,
    )

    day_briefs = []
    day_plan_rows = []
    for idx, row in enumerate(day_inputs, start=1):
        week_number = reasoning_week_number(idx, num_days=num_days, num_weeks=num_weeks)
        brief = build_editorial_day_brief(
            day_number=idx,
            scripture_reference=str(row["scripture_reference"]).strip(),
            scripture_text=str(row["scripture_text"]).strip(),
            study_window_reference=str(row["study_window_reference"]).strip(),
            passage_resources=passage_resources,
        )
        brief = replace(brief, week_number=week_number)
        day_briefs.append(brief)
        day_plan_rows.append(
            {
                "day_number": str(idx),
                "week_number": str(week_number),
                "topic": topic,
                "scripture_reference": str(row["scripture_reference"]).strip(),
                "study_window_reference": str(row["study_window_reference"]).strip(),
            }
        )
    day_briefs = differentiate_day_briefs(day_briefs)
    return build_editorial_artifact(
        topic=topic,
        num_days=num_days,
        source_reference=source_reference,
        day_plan_rows=day_plan_rows,
        day_briefs=day_briefs,
        passage_resources=passage_resources,
    )
