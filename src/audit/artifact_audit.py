"""artifact_audit.py — Phase 010 deterministic artifact integrity audit.

Reports integrity state of GroundingMap and PrayerTraceMap artifacts
for a list of DailyDevotionals.

Contract:
- Never raises; always returns structured results.
- Never mutates input.
- Results sorted by devotional_id ascending.
- No logging, no printing, no CWD dependency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from pydantic import ValidationError

from src.grounding_store.harness import validate_grounding_map_artifact
from src.grounding_store.store import GroundingMapStore
from src.models.devotional import DailyDevotional, PrayerSection, SectionApprovalStatus
from src.prayer_trace_store.store import PrayerTraceMapStore
from src.validation.prayer import validate_prayer

# ---------------------------------------------------------------------------
# Stub prayer section
# Used to call validate_prayer() to exercise PRAYER_TRACE_MAP check only.
# 150 words; starts with "Father" (satisfies PRAYER_TRINITY_ADDRESS).
# ---------------------------------------------------------------------------
_STUB_PRAYER_WORD_COUNT = 150
_STUB_PRAYER_TEXT = "Father, " + " ".join(["grace"] * (_STUB_PRAYER_WORD_COUNT - 1))
_PRAYER_TRACE_CHECK_ID = "PRAYER_TRACE_MAP"


@dataclass
class ArtifactAuditResult:
    devotional_id: str
    grounding_status: str    # "absent" | "pass" | "missing" | "invalid"
    prayer_trace_status: str  # "absent" | "pass" | "missing" | "invalid"
    details: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _audit_grounding(gm_id: str) -> Tuple[str, List[str]]:
    """Return (status, detail_messages) for a single GroundingMap artifact."""
    if not gm_id:
        return "absent", []

    store = GroundingMapStore(root_dir=GroundingMapStore.DEFAULT_ROOT)
    try:
        assessments = validate_grounding_map_artifact(gm_id, store)
        failing = [a for a in assessments if a.result == "fail"]
        if failing:
            return "invalid", [
                f"grounding {a.check_id}: {a.reason_code}" for a in failing
            ]
        return "pass", []
    except KeyError:
        return "missing", [f"grounding: artifact {gm_id!r} not found in store"]
    except ValidationError as exc:
        return "invalid", [
            f"grounding: artifact {gm_id!r} failed schema validation: {exc}"
        ]


def _audit_prayer_trace(ptm_id: str) -> Tuple[str, List[str]]:
    """Return (status, detail_messages) for a single PrayerTraceMap artifact."""
    if not ptm_id:
        return "absent", []

    store = PrayerTraceMapStore(root_dir=PrayerTraceMapStore.DEFAULT_ROOT)
    try:
        trace_map = store.load(ptm_id)
        stub_section = PrayerSection(
            text=_STUB_PRAYER_TEXT,
            word_count=_STUB_PRAYER_WORD_COUNT,
            prayer_trace_map_id=ptm_id,
            approval_status=SectionApprovalStatus.PENDING,
        )
        assessments = validate_prayer(stub_section, prayer_trace_map=trace_map)
        ptm_assessments = [
            a for a in assessments if a.check_id == _PRAYER_TRACE_CHECK_ID
        ]
        if not ptm_assessments:
            return "invalid", [
                f"prayer_trace: artifact {ptm_id!r} produced no PRAYER_TRACE_MAP assessment"
            ]
        if ptm_assessments[0].result == "pass":
            return "pass", []
        return "invalid", [
            f"prayer_trace {ptm_assessments[0].check_id}: {ptm_assessments[0].reason_code}"
        ]
    except KeyError:
        return "missing", [f"prayer_trace: artifact {ptm_id!r} not found in store"]
    except ValidationError as exc:
        return "invalid", [
            f"prayer_trace: artifact {ptm_id!r} failed schema validation: {exc}"
        ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def audit_devotionals(
    devotionals: List[DailyDevotional],
) -> List[ArtifactAuditResult]:
    """Deterministically audit artifact integrity for a list of DailyDevotionals.

    For each devotional:
    - Checks GroundingMap if ``exposition.grounding_map_id`` is truthy.
    - Checks PrayerTraceMap if ``prayer.prayer_trace_map_id`` is truthy.

    Status values: ``"absent"`` | ``"pass"`` | ``"missing"`` | ``"invalid"``

    Never raises. Returns results sorted by ``devotional_id`` ascending.
    """
    results: List[ArtifactAuditResult] = []

    for day in devotionals:
        dev_id = f"day-{day.day_number}"

        gm_status, gm_details = _audit_grounding(day.exposition.grounding_map_id)
        ptm_status, ptm_details = _audit_prayer_trace(day.prayer.prayer_trace_map_id)

        results.append(
            ArtifactAuditResult(
                devotional_id=dev_id,
                grounding_status=gm_status,
                prayer_trace_status=ptm_status,
                details=gm_details + ptm_details,
            )
        )

    return sorted(results, key=lambda r: r.devotional_id)
