"""exposition.py — FR-74 deterministic exposition validator.

Checks word count (computed from text), second-person voice prohibition,
and Grounding Map structural completeness.
"""
from __future__ import annotations

import re
from typing import Optional

from src.models.artifacts import GroundingMap
from src.models.devotional import ExpositionSection
from src.models.validation import ValidatorAssessment

_WORD_COUNT_MIN = 500
_WORD_COUNT_MAX = 700

# Second-person pronoun pattern — presence in exposition is a violation.
_SECOND_PERSON = re.compile(r"\b(you|your)\b", re.IGNORECASE)


def _pass(check_id: str) -> ValidatorAssessment:
    return ValidatorAssessment(
        check_id=check_id, result="pass", reason_code="", explanation=""
    )


def validate_exposition(
    section: ExpositionSection,
    grounding_map: Optional[GroundingMap] = None,
) -> list[ValidatorAssessment]:
    """Run all deterministic checks on an ExpositionSection.

    Word count is recomputed from section.text; the stored word_count
    field is not used.

    If grounding_map is None, the EXPOSITION_GROUNDING_MAP check is
    omitted from the returned list.
    """
    results: list[ValidatorAssessment] = []

    # --- EXPOSITION_WORD_COUNT ---
    computed = len(section.text.split())
    if _WORD_COUNT_MIN <= computed <= _WORD_COUNT_MAX:
        results.append(_pass("EXPOSITION_WORD_COUNT"))
    else:
        results.append(
            ValidatorAssessment(
                check_id="EXPOSITION_WORD_COUNT",
                result="fail",
                reason_code="EXPOSITION_WORD_COUNT_VIOLATION",
                explanation=(
                    f"Exposition is {computed} words; "
                    f"must be {_WORD_COUNT_MIN}–{_WORD_COUNT_MAX}."
                ),
                evidence=f"computed word count: {computed}",
            )
        )

    # --- EXPOSITION_VOICE ---
    match = _SECOND_PERSON.search(section.text)
    if match:
        results.append(
            ValidatorAssessment(
                check_id="EXPOSITION_VOICE",
                result="fail",
                reason_code="EXPOSITION_SECOND_PERSON_VIOLATION",
                explanation=(
                    "Exposition must use communal voice (we/our); "
                    "second-person (you/your) is prohibited."
                ),
                evidence=match.group(0),
            )
        )
    else:
        results.append(_pass("EXPOSITION_VOICE"))

    # --- EXPOSITION_GROUNDING_MAP (optional) ---
    if grounding_map is not None:
        entries = grounding_map.entries
        incomplete = [
            e
            for e in entries
            if not e.sources_retrieved or not e.excerpts_used
        ]
        if len(entries) == 4 and not incomplete:
            results.append(_pass("EXPOSITION_GROUNDING_MAP"))
        else:
            detail = (
                f"{len(entries)} entries (expected 4)"
                if len(entries) != 4
                else f"{len(incomplete)} entries missing sources or excerpts"
            )
            results.append(
                ValidatorAssessment(
                    check_id="EXPOSITION_GROUNDING_MAP",
                    result="fail",
                    reason_code="EXPOSITION_GROUNDING_MAP_INCOMPLETE",
                    explanation=(
                        "Grounding Map must have exactly 4 non-empty entries. "
                        f"Found: {detail}."
                    ),
                    evidence=detail,
                )
            )

    return results
