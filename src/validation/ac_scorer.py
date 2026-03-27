"""ac_scorer.py — PRD v16 Acceptance Criteria scoring module.

Maps existing deterministic validators to numbered AC criteria and computes
an aggregate AC score alongside trainer scores so divergence can be detected.

AC coverage:
  Exposition  — AC-09, AC-10 (deterministic); AC-01–08, AC-11 not evaluated
  Be Still    — AC-12, AC-16 (deterministic); AC-13–15, AC-17 not evaluated
  Action Steps— AC-18, AC-19 (deterministic); AC-20a–b not evaluated
  Prayer      — AC-21, AC-27, AC-31 (deterministic); AC-22–26, AC-28–30, AC-32 not evaluated

"not_evaluated" means no deterministic check exists yet — LLM trainer handles it.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from src.models.artifacts import GroundingMap, PrayerTraceMap
from src.models.devotional import (
    ActionStepsSection,
    BeStillSection,
    ExpositionSection,
    PrayerSection,
)
from src.validation.action_steps import validate_action_steps
from src.validation.be_still import validate_be_still
from src.validation.exposition import validate_exposition
from src.validation.prayer import validate_prayer


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _from_validator(check_id: str, assessments: list) -> dict[str, Any]:
    """Extract a single ValidatorAssessment by check_id as an AC result dict."""
    for a in assessments:
        if a.check_id == check_id:
            return {
                "status": a.result,  # "pass" | "fail"
                "reason": a.explanation or a.reason_code,
                "weight": 1,
            }
    return {"status": "not_evaluated", "reason": "no deterministic check", "weight": 0}


def _not_evaluated(reason: str = "requires LLM evaluation") -> dict[str, Any]:
    return {"status": "not_evaluated", "reason": reason, "weight": 0}


# ---------------------------------------------------------------------------
# Per-section scorers
# ---------------------------------------------------------------------------

def score_exposition(
    section: ExpositionSection,
    grounding_map: Optional[GroundingMap] = None,
) -> dict[str, dict[str, Any]]:
    """Score exposition section against AC-01 through AC-11."""
    assessments = validate_exposition(section, grounding_map=grounding_map)
    return {
        "AC-01": _not_evaluated("four-paragraph structure requires LLM"),
        "AC-02": _not_evaluated("opening declaration requires LLM"),
        "AC-03": _not_evaluated("canonical context paragraph requires LLM"),
        "AC-04": _not_evaluated("theological paragraph sequence requires LLM"),
        "AC-05": _from_validator("EXPOSITION_GROUNDING_MAP", assessments)
                 if grounding_map is not None
                 else _not_evaluated("grounding map not provided"),
        "AC-06": _not_evaluated("experiential bridge cultural tension requires LLM"),
        "AC-07": _not_evaluated("bridge christological grounding requires LLM"),
        "AC-08": _not_evaluated("bridge felt-need close requires LLM"),
        "AC-09": _from_validator("EXPOSITION_VOICE", assessments),
        "AC-10": _from_validator("EXPOSITION_WORD_COUNT", assessments),
        "AC-11": _not_evaluated("literary genre handling requires LLM"),
    }


def score_be_still(section: BeStillSection) -> dict[str, dict[str, Any]]:
    """Score Be Still section against AC-12 through AC-17."""
    assessments = validate_be_still(section)
    return {
        "AC-12": _from_validator("BE_STILL_PROMPT_COUNT", assessments),
        "AC-13": _not_evaluated("first prompt stillness/receptivity requires LLM"),
        "AC-14": _not_evaluated("inward-to-outward progression requires LLM"),
        "AC-15": _not_evaluated("final prompt felt-need flow requires LLM"),
        "AC-16": _from_validator("BE_STILL_SECOND_PERSON", assessments),
        "AC-17": _not_evaluated("prompts arise from exposition requires LLM"),
    }


def score_action_steps(section: ActionStepsSection) -> dict[str, dict[str, Any]]:
    """Score Action Steps section against AC-18 through AC-20b."""
    assessments = validate_action_steps(section)
    return {
        "AC-18": _from_validator("ACTION_STEPS_CONNECTOR_PHRASE", assessments),
        "AC-19": _from_validator("ACTION_STEPS_COUNT", assessments),
        "AC-20a": _not_evaluated("active expectation/partnership requires LLM"),
        "AC-20b": _not_evaluated("unfamiliarity grounded in faithfulness requires LLM"),
    }


def score_prayer(
    section: PrayerSection,
    prayer_trace_map: Optional[PrayerTraceMap] = None,
) -> dict[str, dict[str, Any]]:
    """Score Prayer section against AC-21 through AC-32."""
    assessments = validate_prayer(section, prayer_trace_map=prayer_trace_map)
    return {
        "AC-21": _from_validator("PRAYER_TRINITY_ADDRESS", assessments),
        "AC-22": _not_evaluated("opening names attribute/action requires LLM"),
        "AC-23": _not_evaluated("names human condition requires LLM"),
        "AC-24": _not_evaluated("echoes scripture language requires LLM"),
        "AC-25": _not_evaluated("petition traceable to verse requires LLM"),
        "AC-26": _not_evaluated("sounds like laying hold of God requires LLM"),
        "AC-27": _from_validator("PRAYER_TRACE_MAP", assessments)
                 if prayer_trace_map is not None
                 else _not_evaluated("prayer trace map not provided"),
        "AC-28": _not_evaluated("closes with trust/surrender requires LLM"),
        "AC-29": _not_evaluated("passage identifiable from prayer requires LLM"),
        "AC-30": _not_evaluated("cohesive arc requires LLM"),
        "AC-31": _from_validator("PRAYER_WORD_COUNT", assessments),
        "AC-32": _not_evaluated("no doctrinal contradiction requires LLM"),
    }


# ---------------------------------------------------------------------------
# Aggregate scoring
# ---------------------------------------------------------------------------

def calculate_ac_score(ac_results: dict[str, dict[str, Any]]) -> int:
    """Compute weighted AC pass percentage (0–100, int).

    Only ACs with weight > 0 (i.e. evaluated) count toward the score.
    Returns 0 if no evaluated ACs exist.
    """
    total_weight = sum(
        v.get("weight", 0) for v in ac_results.values() if v.get("weight", 0) > 0
    )
    if total_weight == 0:
        return 0
    pass_weight = sum(
        v.get("weight", 0)
        for v in ac_results.values()
        if v.get("status") == "pass" and v.get("weight", 0) > 0
    )
    return round(pass_weight / total_weight * 100)


def detect_divergence(trainer_score: int, ac_score: int) -> str:
    """Detect divergence between trainer score and AC compliance score.

    Returns:
        "suspicious_pass"      — trainer rewards output that ACs reject
        "suppressed_quality"   — trainer penalises output that ACs would pass
        "aligned"              — scores agree (both high, both low, or mixed without extreme gap)

    Only fires when both scores are based on evaluated ACs (ac_score > 0).
    """
    if ac_score == 0:
        return "aligned"  # no evaluated ACs — can't determine divergence
    if trainer_score >= 70 and ac_score < 50:
        return "suspicious_pass"
    if trainer_score < 50 and ac_score >= 70:
        return "suppressed_quality"
    return "aligned"


# ---------------------------------------------------------------------------
# Convenience: score any worker output by name
# ---------------------------------------------------------------------------

def score_worker_output(
    worker_name: str,
    section: Any,
    *,
    grounding_map: Optional[GroundingMap] = None,
    prayer_trace_map: Optional[PrayerTraceMap] = None,
) -> dict[str, dict[str, Any]]:
    """Dispatch to the correct scorer by worker name.

    Returns an empty dict for workers with no AC scoring defined.
    """
    if worker_name in ("exposition_writer", "exposition"):
        return score_exposition(section, grounding_map=grounding_map)
    if worker_name in ("be_still_writer", "be_still"):
        return score_be_still(section)
    if worker_name in ("action_writer", "action_steps"):
        return score_action_steps(section)
    if worker_name in ("prayer_writer", "prayer"):
        return score_prayer(section, prayer_trace_map=prayer_trace_map)
    return {}


def ac_scores_to_metrics(ac_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Serialise ac_results for storage in log_experiment metrics.

    Returns a dict with:
        ac_scores  — JSON string of the full AC result dict
        ac_score   — integer aggregate score (0–100)
    """
    return {
        "ac_scores": json.dumps(ac_results),
        "ac_score": calculate_ac_score(ac_results),
    }
