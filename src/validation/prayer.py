"""prayer.py — FR-77 deterministic prayer validator.

Checks word count (computed from text), Trinity address presence,
and Prayer Trace Map structural completeness.
"""
from __future__ import annotations

import re
from typing import Optional

from src.models.artifacts import PrayerTraceMap
from src.models.devotional import PrayerSection
from src.models.validation import ValidatorAssessment

_WORD_COUNT_MIN = 120
_WORD_COUNT_MAX = 200

# At least one Trinity name must appear in the prayer.
_TRINITY_PATTERN = re.compile(
    r"\b(Father|Jesus|Lord|Spirit|God)\b", re.IGNORECASE
)

_VALID_SOURCE_TYPES = {"scripture", "exposition", "be_still"}


def _pass(check_id: str) -> ValidatorAssessment:
    return ValidatorAssessment(
        check_id=check_id, result="pass", reason_code="", explanation=""
    )


def validate_prayer(
    section: PrayerSection,
    prayer_trace_map: Optional[PrayerTraceMap] = None,
) -> list[ValidatorAssessment]:
    """Run all deterministic checks on a PrayerSection.

    Word count is recomputed from section.text; the stored word_count
    field is not used.

    If prayer_trace_map is None, the PRAYER_TRACE_MAP check is
    omitted from the returned list.
    """
    results: list[ValidatorAssessment] = []

    # --- PRAYER_WORD_COUNT ---
    computed = len(section.text.split())
    if _WORD_COUNT_MIN <= computed <= _WORD_COUNT_MAX:
        results.append(_pass("PRAYER_WORD_COUNT"))
    else:
        results.append(
            ValidatorAssessment(
                check_id="PRAYER_WORD_COUNT",
                result="fail",
                reason_code="PRAYER_WORD_COUNT_VIOLATION",
                explanation=(
                    f"Prayer is {computed} words; "
                    f"must be {_WORD_COUNT_MIN}–{_WORD_COUNT_MAX}."
                ),
                evidence=f"computed word count: {computed}",
            )
        )

    # --- PRAYER_TRINITY_ADDRESS ---
    match = _TRINITY_PATTERN.search(section.text)
    if match:
        results.append(_pass("PRAYER_TRINITY_ADDRESS"))
    else:
        results.append(
            ValidatorAssessment(
                check_id="PRAYER_TRINITY_ADDRESS",
                result="fail",
                reason_code="PRAYER_TRINITY_ADDRESS_MISSING",
                explanation=(
                    "Prayer must address at least one person of the Trinity "
                    "(Father, Jesus, Lord, Spirit, or God)."
                ),
                evidence="no Trinity name found in prayer text",
            )
        )

    # --- PRAYER_TRACE_MAP (optional) ---
    if prayer_trace_map is not None:
        entries = prayer_trace_map.entries
        invalid = [
            e for e in entries if e.source_type not in _VALID_SOURCE_TYPES
        ]
        if entries and not invalid:
            results.append(_pass("PRAYER_TRACE_MAP"))
        else:
            if not entries:
                detail = "Prayer Trace Map has no entries"
            else:
                detail = (
                    f"{len(invalid)} entries have invalid source_type; "
                    f"must be one of {sorted(_VALID_SOURCE_TYPES)}"
                )
            results.append(
                ValidatorAssessment(
                    check_id="PRAYER_TRACE_MAP",
                    result="fail",
                    reason_code="PRAYER_TRACE_MAP_INCOMPLETE",
                    explanation=(
                        "All prayer elements must be traceable to scripture, "
                        f"exposition, or be_still. {detail}."
                    ),
                    evidence=detail,
                )
            )

    return results
