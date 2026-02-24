"""orchestrator.py — FR-73 validation pass orchestrator.

Calls all section validators on a DailyDevotional and aggregates
the resulting ValidatorAssessments. Does not perform rewrites;
does not invoke rewrite_router. Returns assessments only.
"""
from __future__ import annotations

from typing import Optional

from src.models.artifacts import GroundingMap, PrayerTraceMap
from src.models.devotional import DailyDevotional
from src.models.validation import ValidatorAssessment
from src.validation.action_steps import validate_action_steps
from src.validation.be_still import validate_be_still
from src.validation.doctrinal import check_doctrinal
from src.validation.exposition import validate_exposition
from src.validation.prayer import validate_prayer


def validate_daily_devotional(
    day: DailyDevotional,
    grounding_map: Optional[GroundingMap] = None,
    prayer_trace_map: Optional[PrayerTraceMap] = None,
) -> list[ValidatorAssessment]:
    """Run all deterministic validators on a DailyDevotional.

    Aggregates assessments from exposition, be_still, action_steps,
    prayer validators, and doctrinal guardrail checks on both
    exposition and prayer text.

    Args:
        day: The DailyDevotional to validate.
        grounding_map: Optional GroundingMap for the exposition section.
                       If None, EXPOSITION_GROUNDING_MAP check is omitted.
        prayer_trace_map: Optional PrayerTraceMap for the prayer section.
                          If None, PRAYER_TRACE_MAP check is omitted.

    Returns:
        All ValidatorAssessments in call order:
          1. Exposition section checks
          2. Be Still section checks
          3. Action Steps section checks
          4. Prayer section checks
          5. Doctrinal checks on exposition text
          6. Doctrinal checks on prayer text
    """
    assessments: list[ValidatorAssessment] = []

    assessments.extend(validate_exposition(day.exposition, grounding_map=grounding_map))
    assessments.extend(validate_be_still(day.be_still))
    assessments.extend(validate_action_steps(day.action_steps))
    assessments.extend(validate_prayer(day.prayer, prayer_trace_map=prayer_trace_map))
    assessments.extend(check_doctrinal(day.exposition.text))
    assessments.extend(check_doctrinal(day.prayer.text))

    return assessments
