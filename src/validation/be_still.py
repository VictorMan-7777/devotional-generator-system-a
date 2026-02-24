"""be_still.py — FR-75 deterministic Be Still section validator.

Checks prompt count (3–5) and that at least one prompt uses
explicit second-person language (you/your).
"""
from __future__ import annotations

import re

from src.models.devotional import BeStillSection
from src.models.validation import ValidatorAssessment

_PROMPT_COUNT_MIN = 3
_PROMPT_COUNT_MAX = 5

# At least one prompt must contain explicit second-person language.
_SECOND_PERSON = re.compile(r"\b(you|your)\b", re.IGNORECASE)


def _pass(check_id: str) -> ValidatorAssessment:
    return ValidatorAssessment(
        check_id=check_id, result="pass", reason_code="", explanation=""
    )


def validate_be_still(section: BeStillSection) -> list[ValidatorAssessment]:
    """Run all deterministic checks on a BeStillSection."""
    results: list[ValidatorAssessment] = []

    # --- BE_STILL_PROMPT_COUNT ---
    count = len(section.prompts)
    if _PROMPT_COUNT_MIN <= count <= _PROMPT_COUNT_MAX:
        results.append(_pass("BE_STILL_PROMPT_COUNT"))
    else:
        results.append(
            ValidatorAssessment(
                check_id="BE_STILL_PROMPT_COUNT",
                result="fail",
                reason_code="BE_STILL_PROMPT_COUNT_VIOLATION",
                explanation=(
                    f"Be Still section has {count} prompts; "
                    f"must have {_PROMPT_COUNT_MIN}–{_PROMPT_COUNT_MAX}."
                ),
                evidence=f"prompt count: {count}",
            )
        )

    # --- BE_STILL_SECOND_PERSON ---
    # At least one prompt must contain explicit second-person language.
    has_second_person = any(
        _SECOND_PERSON.search(p) for p in section.prompts
    )
    if has_second_person:
        results.append(_pass("BE_STILL_SECOND_PERSON"))
    else:
        results.append(
            ValidatorAssessment(
                check_id="BE_STILL_SECOND_PERSON",
                result="fail",
                reason_code="BE_STILL_SECOND_PERSON_ABSENT",
                explanation=(
                    "Be Still prompts must address the reader directly; "
                    "no prompt contains explicit second-person language (you/your)."
                ),
                evidence="none of the prompts contain 'you' or 'your'",
            )
        )

    return results
