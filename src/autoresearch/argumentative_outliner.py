"""argumentative_outliner.py — Cumulative-argument outline builder for Hebrews-style epistles.

Implements Stage 1 argumentative outlining per the design session results agreed
by Theological Reviewer and Outliner Trainer (2026-03-25).

Handles passages with cumulative argumentative structures where:
- Each day must advance a logical argument (C2, C8)
- Warning passages require full antecedent enforcement both TO and FROM the warning day (C3)
- Warning passages must not be routed to ethical-didactic or application subtypes (C4)
- Classifier receives full passage context, not day-in-isolation (C1)
- week_to_week_bridge feeds each successive week's prior_bridge parameter (C6)
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field

from src.autoresearch.reasoning_outliner_core import (
    build_reasoning_week_plans,
    reasoning_week_number,
)
from src.llm.router import get_llm_client
from src.models.pipeline import (
    EditorialBuildArtifact,
    EditorialDayBriefRecord,
    EditorialDayPlanRow,
    PassageResourceBundle,
)


# ── Pydantic schema — matches Outliner Trainer authoritative spec exactly (C5) ──

class ArgumentativeDay(BaseModel):
    day_subtype: str = Field(..., pattern=r"^(argument_step|warning_beat|exhortation)$")
    arg_step_index: Optional[int] = None
    logical_antecedent: str = Field(..., min_length=20)
    arg_advance_claim: str = Field(..., min_length=15)
    warning_slot: bool = False
    warning_position: Optional[str] = Field(default=None, pattern=r"^(mid_week|end_of_week)$")


class WeekOutline(BaseModel):
    week_opening_tension: str = Field(..., min_length=10)
    week_closing_location: str = Field(..., min_length=10)
    days: list[ArgumentativeDay] = Field(..., min_length=5, max_length=7)
    week_to_week_bridge: Optional[str] = None
    stakes_level: int = Field(..., ge=1, le=5)


# ── Hard-fail validator (C2, C3, C4, C8) ──

def validate_outline(week: WeekOutline) -> Optional[str]:
    """Return pipe-joined error string on failure, None if outline passes all hard-fail checks."""
    errors: list[str] = []
    arg_indices: list[int] = []

    for i, day in enumerate(week.days):
        # arg_step_index rules
        if day.day_subtype == "argument_step":
            if day.arg_step_index is None:
                errors.append(f"Day {i+1}: argument_step missing arg_step_index")
            else:
                arg_indices.append(day.arg_step_index)
        else:
            if day.arg_step_index is not None:
                errors.append(f"Day {i+1}: non-argument day must have arg_step_index null")

        # Full antecedent enforcement on days 2+ (C2 — same check as argument days)
        if i > 0:
            antecedent = day.logical_antecedent.strip()
            if len(antecedent) < 30:
                errors.append(f"Day {i+1}: logical_antecedent too short (< 30 chars) — must be specific")
            lower = antecedent.lower()
            if lower in ("", "none", "n/a") or lower.startswith("generic") or lower.startswith("day"):
                errors.append(f"Day {i+1}: logical_antecedent is generic or empty")

        # warning_slot: antecedent must be writable TO this day AND FROM this day (C3)
        if day.warning_slot:
            antecedent = day.logical_antecedent.strip()
            if len(antecedent) < 30:
                errors.append(
                    f"Day {i+1}: warning_slot antecedent too short — "
                    "must show a writable logical bridge TO this warning day"
                )
            # The day after a warning must also have a specific antecedent bridging FROM it
            if i + 1 < len(week.days):
                next_antecedent = week.days[i + 1].logical_antecedent.strip()
                if len(next_antecedent) < 30:
                    errors.append(
                        f"Day {i+2}: antecedent after warning_slot too short — "
                        "must show a writable logical bridge FROM the warning day"
                    )

    # arg_step_index must be strictly increasing (C8)
    if len(arg_indices) > 1:
        for j in range(1, len(arg_indices)):
            if arg_indices[j] <= arg_indices[j - 1]:
                errors.append("arg_step_index values are not strictly increasing across argument_step days")
                break
    if len(arg_indices) != len(set(arg_indices)):
        errors.append("arg_step_index values contain duplicates")

    # Closing must not be semantically equivalent to opening (C8)
    opening = week.week_opening_tension.lower().strip()
    closing = week.week_closing_location.lower().strip()
    if opening == closing or closing in opening or opening in closing:
        errors.append(
            "week_closing_location is semantically equivalent to week_opening_tension — "
            "no argumentative advance was made"
        )

    return "|".join(errors) if errors else None


# ── LLM prompt template ──

_PROMPT = """You are outlining a week of devotionals on {ref} as a cumulative argument.

FULL PASSAGE TEXT (use the entire argument context to classify each day — do not classify in isolation):
{text}

PRIOR WEEK BRIDGE (what the previous week's argument established — feeds this week's opening tension):
{prior}

HEBREWS WARNING PASSAGES — these must be treated as warning_beat days with full antecedent enforcement:
- Heb 5:11–6:12: mid-week warning (Week 3). Must have a logical_antecedent bridge TO it from the preceding argument AND from it to Melchizedek (7:1ff). Hard fail if routed to ethical-didactic or application.
- Heb 10:26–31: end-of-week warning (Week 5). Must have a logical_antecedent bridge TO and FROM it. Hard fail if routed as an application slot.

TASK: Output ONLY a valid JSON object — no markdown, no explanation.

{{
  "week_opening_tension": "<question or tension that Day 1 opens>",
  "week_closing_location": "<where the final day lands in the argument — must be genuinely advanced from tension>",
  "days": [
    {{
      "day_subtype": "argument_step" | "warning_beat" | "exhortation",
      "arg_step_index": <int sequential — null if warning_beat or exhortation>,
      "logical_antecedent": "<Because we established X, today we address Y — specific, non-generic, >= 30 chars>",
      "arg_advance_claim": "<what new argumentative ground this day covers>",
      "warning_slot": <true only if this day contains Heb 5:11-6:12 or 10:26-31, else false>,
      "warning_position": "mid_week" | "end_of_week" | null
    }}
  ],
  "week_to_week_bridge": "<premise this week's conclusion provides to next week — null for the final week>",
  "stakes_level": <int 1-5, must escalate week-over-week across the 5-week Hebrews arc>
}}

Output exactly {num_days} day entries. logical_antecedent must be specific and >= 30 chars on every day 2+.
arg_step_index must be strictly increasing across argument_step days.
week_closing_location must differ meaningfully from week_opening_tension."""


# ── Public entry point ──

def build_argumentative_outline_artifact(
    *,
    topic: str,
    source_reference: str,
    num_days: int,
    num_weeks: int,
    day_inputs: list[dict[str, str]],
    passage_resources: PassageResourceBundle | None = None,
) -> EditorialBuildArtifact:
    """Build a cumulative-argument outline for Hebrews-style epistles.

    Phase 1 — Per-week generation (Stage 1):
      For each week: LLM generates WeekOutline, hard-fail validator checks it,
      warning_position is set post-validation, prior bridge is carried forward.

    Phase 2 — Arc coherence evaluation (Stage 2):
      All WeekOutlines are evaluated together for 5-week arc coherence.
      SF violations raise ValueError (hard fail). SD flags are logged but do not fail.

    Phase 3 — Artifact assembly:
      WeekOutlines are converted to EditorialDayPlanRow + EditorialDayBriefRecord.
    """
    from src.autoresearch.arc_coherence_evaluator import evaluate_arc_coherence

    llm = get_llm_client(worker="outliner")
    days_per_week = max(1, num_days // num_weeks) if num_weeks > 0 else num_days

    # Full text for C1 — classifier always receives the full passage context
    full_text = "\n\n".join(
        row.get("scripture_text", "").strip() for row in day_inputs
    ).strip() or source_reference

    # ── Phase 1: collect all WeekOutlines ──
    week_outlines: list[WeekOutline] = []
    week_day_inputs_list: list[list[dict]] = []
    prior_bridge: Optional[str] = None

    for week_idx in range(num_weeks):
        week_number = week_idx + 1
        week_start = week_idx * days_per_week
        week_end = week_start + days_per_week if week_idx < num_weeks - 1 else num_days
        week_day_inputs = day_inputs[week_start:week_end]
        week_num_days = len(week_day_inputs)

        week_ref = (
            f"{source_reference} (Week {week_number} of {num_weeks})"
            if num_weeks > 1
            else source_reference
        )

        prompt = _PROMPT.format(
            ref=week_ref,
            text=full_text,
            prior=prior_bridge or "None — this is Week 1",
            num_days=week_num_days,
        )

        raw = llm.generate(prompt, timeout=300)
        json_str = _extract_json(raw)
        week_outline = WeekOutline.model_validate_json(json_str)

        # Per-week hard-fail validation (C2, C3, C4, C8)
        err = validate_outline(week_outline)
        if err:
            raise ValueError(f"HARD_FAIL week {week_number} ({source_reference}): {err}")

        # Post-validation: assign warning_position (C9)
        updated_days = []
        for i, day in enumerate(week_outline.days):
            if day.warning_slot:
                position = "mid_week" if i in (1, 2) else "end_of_week" if i >= 3 else None
                updated_days.append(day.model_copy(update={"warning_position": position}))
            else:
                updated_days.append(day)
        week_outline = week_outline.model_copy(update={"days": updated_days})

        prior_bridge = week_outline.week_to_week_bridge
        week_outlines.append(week_outline)
        week_day_inputs_list.append(week_day_inputs)

    # ── Phase 2: arc coherence evaluation (Stage 2) ──
    if len(week_outlines) > 1:
        arc_report = evaluate_arc_coherence(week_outlines)
        if arc_report.verdict == "fail":
            raise ValueError(
                f"ARC_COHERENCE_FAIL ({source_reference}): {arc_report.summary} "
                f"SF violations: {arc_report.sf_violations}"
            )
        # SD flags are logged — they inform revision but do not block
        if arc_report.sd_flags:
            print(
                f"[arc_coherence] REVISE flags on {source_reference}: "
                f"{arc_report.sd_flags} — {arc_report.summary}"
            )

    # ── Phase 3: convert to EditorialBuildArtifact ──
    day_plan: list[EditorialDayPlanRow] = []
    day_briefs: list[EditorialDayBriefRecord] = []

    for week_idx, (week_outline, week_day_inputs) in enumerate(
        zip(week_outlines, week_day_inputs_list)
    ):
        week_number = week_idx + 1
        week_start = week_idx * days_per_week

        for local_idx, (day, row) in enumerate(zip(week_outline.days, week_day_inputs)):
            global_day_number = week_start + local_idx + 1
            scripture_ref = str(row.get("scripture_reference", "")).strip()
            study_window = str(row.get("study_window_reference", "")).strip()
            key_verse = str(row.get("key_verse_reference", "")).strip()

            day_plan.append(
                EditorialDayPlanRow(
                    day_number=global_day_number,
                    week_number=week_number,
                    topic=topic,
                    scripture_reference=scripture_ref,
                    study_window_reference=study_window,
                )
            )
            day_briefs.append(
                EditorialDayBriefRecord(
                    day_number=global_day_number,
                    week_number=week_number,
                    scripture_reference=scripture_ref,
                    study_window_reference=study_window,
                    key_verse_reference=key_verse,
                    day_title=f"{scripture_ref} — {day.arg_advance_claim[:60]}",
                    focus_clause=day.logical_antecedent,
                    pastoral_burden=day.arg_advance_claim,
                    genre="epistle",
                    scene_summary=(
                        f"{week_outline.week_opening_tension} → {day.arg_advance_claim}"
                    ),
                    theological_lane=_theological_lane(day.day_subtype),
                    application_lane=(
                        "warning-response" if day.warning_slot else "argument-application"
                    ),
                    forbidden_drifts=_forbidden_drifts(day.day_subtype),
                    key_terms=[],
                )
            )

    week_plans = build_reasoning_week_plans(day_briefs)
    return EditorialBuildArtifact(
        topic=topic,
        num_days=num_days,
        source_reference=source_reference,
        week_count=num_weeks,
        passage_resources=passage_resources,
        day_plan=day_plan,
        day_briefs=day_briefs,
        week_plans=week_plans,
    )


# ── Helpers ──

def _extract_json(raw: str) -> str:
    """Strip markdown fences and extract the outermost JSON object."""
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        return fence.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        return raw[start : end + 1]
    return raw


def _theological_lane(day_subtype: str) -> str:
    return {
        "argument_step": "christological-argument",
        "warning_beat": "atonement-warning",
        "exhortation": "pastoral-exhortation",
    }.get(day_subtype, "christological-argument")


def _forbidden_drifts(day_subtype: str) -> list[str]:
    base = [
        "ethical-didactic application divorced from Christological ground",
        "moralistic framing without atonement foundation",
    ]
    if day_subtype == "warning_beat":
        base += [
            "routing warning passage as generic exhortation or application slot",
            "softening Hebrews warning into encouragement without logical antecedent",
        ]
    return base
