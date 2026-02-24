"""action_steps.py — FR-76 deterministic Action Steps validator.

Checks item count (1–3) and connector phrase presence.
"""
from __future__ import annotations

from src.models.devotional import ActionStepsSection
from src.models.validation import ValidatorAssessment

_ITEM_COUNT_MIN = 1
_ITEM_COUNT_MAX = 3


def _pass(check_id: str) -> ValidatorAssessment:
    return ValidatorAssessment(
        check_id=check_id, result="pass", reason_code="", explanation=""
    )


def validate_action_steps(section: ActionStepsSection) -> list[ValidatorAssessment]:
    """Run all deterministic checks on an ActionStepsSection."""
    results: list[ValidatorAssessment] = []

    # --- ACTION_STEPS_COUNT ---
    count = len(section.items)
    if _ITEM_COUNT_MIN <= count <= _ITEM_COUNT_MAX:
        results.append(_pass("ACTION_STEPS_COUNT"))
    else:
        results.append(
            ValidatorAssessment(
                check_id="ACTION_STEPS_COUNT",
                result="fail",
                reason_code="ACTION_STEPS_COUNT_VIOLATION",
                explanation=(
                    f"Action Steps has {count} items; "
                    f"must have {_ITEM_COUNT_MIN}–{_ITEM_COUNT_MAX}."
                ),
                evidence=f"item count: {count}",
            )
        )

    # --- ACTION_STEPS_CONNECTOR_PHRASE ---
    if section.connector_phrase and section.connector_phrase.strip():
        results.append(_pass("ACTION_STEPS_CONNECTOR_PHRASE"))
    else:
        results.append(
            ValidatorAssessment(
                check_id="ACTION_STEPS_CONNECTOR_PHRASE",
                result="fail",
                reason_code="ACTION_STEPS_CONNECTOR_PHRASE_MISSING",
                explanation="Action Steps must have a non-empty connector phrase.",
                evidence=repr(section.connector_phrase),
            )
        )

    return results
