"""Phase 009 — Prayer Trace Activation tests.

Tests that validate_daily_devotional() auto-resolves a PrayerTraceMap from the
canonical store when prayer.prayer_trace_map_id is present, and preserves
existing behaviour when it is absent.

Required behaviours:
  1. No id → no exception, no PRAYER_TRACE_MAP check executed.
  2. Id present and stored → check executes and passes.
  3. Id present but missing → KeyError propagates (no silent skip).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.generation.generators import MockSectionGenerator
from src.models.artifacts import PrayerTraceMap, PrayerTraceMapEntry
from src.models.devotional import PrayerSection, SectionApprovalStatus
from src.prayer_trace_store.store import PrayerTraceMapStore
from src.validation.orchestrator import validate_daily_devotional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_trace_map(ptm_id: str = "ptm_test_1") -> PrayerTraceMap:
    return PrayerTraceMap(
        id=ptm_id,
        prayer_id="prayer-phase009-test",
        entries=[
            PrayerTraceMapEntry(
                element_text="Father, thank you for your grace.",
                source_type="scripture",
                source_reference="Romans 8:28",
            ),
            PrayerTraceMapEntry(
                element_text="Let your Spirit guide every step.",
                source_type="exposition",
                source_reference="Paragraph 1: grace of God.",
            ),
            PrayerTraceMapEntry(
                element_text="I rest in the stillness of your presence.",
                source_type="be_still",
                source_reference="Prompt 3: Offer that word back to God.",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Test 1 — No id (baseline): behaviour unchanged
# ---------------------------------------------------------------------------


class TestNoId:
    def test_no_exception_when_prayer_trace_map_id_is_empty(self):
        """Empty prayer_trace_map_id → auto-resolution skipped → no exception."""
        day = MockSectionGenerator().generate_day("grace", 1)
        assert day.prayer.prayer_trace_map_id == ""
        assessments = validate_daily_devotional(day)
        assert isinstance(assessments, list)

    def test_prayer_trace_check_absent_when_no_id(self):
        """No id → PRAYER_TRACE_MAP check is not emitted."""
        day = MockSectionGenerator().generate_day("grace", 1)
        assessments = validate_daily_devotional(day)
        check_ids = {a.check_id for a in assessments}
        assert "PRAYER_TRACE_MAP" not in check_ids


# ---------------------------------------------------------------------------
# Test 2 — Id present and stored: check executes and passes
# ---------------------------------------------------------------------------


class TestIdPresentAndStored:
    def test_prayer_trace_check_executes_and_passes(
        self, tmp_path: Path, monkeypatch
    ):
        """Auto-resolution loads the stored map; PRAYER_TRACE_MAP check passes."""
        ptm = _sample_trace_map("ptm_test_1")
        store = PrayerTraceMapStore(tmp_path)
        store.save(ptm)

        monkeypatch.setattr(PrayerTraceMapStore, "DEFAULT_ROOT", tmp_path)

        base_day = MockSectionGenerator().generate_day("grace", 1)
        day = base_day.model_copy(deep=True)
        object.__setattr__(
            day,
            "prayer",
            PrayerSection(
                text=base_day.prayer.text,
                word_count=base_day.prayer.word_count,
                prayer_trace_map_id=ptm.id,
                approval_status=SectionApprovalStatus.PENDING,
            ),
        )

        assessments = validate_daily_devotional(day)

        check_ids = {a.check_id for a in assessments}
        assert "PRAYER_TRACE_MAP" in check_ids, (
            "PRAYER_TRACE_MAP check was not executed — auto-resolution failed"
        )

        ptm_check = next(a for a in assessments if a.check_id == "PRAYER_TRACE_MAP")
        assert ptm_check.result == "pass", (
            f"PRAYER_TRACE_MAP check failed: {ptm_check.reason_code}"
        )


# ---------------------------------------------------------------------------
# Test 3 — Id present but missing: KeyError propagates
# ---------------------------------------------------------------------------


class TestIdPresentButMissing:
    def test_missing_artifact_raises_key_error(self, tmp_path: Path, monkeypatch):
        """Missing artifact → KeyError; id appears in error message."""
        monkeypatch.setattr(PrayerTraceMapStore, "DEFAULT_ROOT", tmp_path)

        base_day = MockSectionGenerator().generate_day("grace", 1)
        day = base_day.model_copy(deep=True)
        object.__setattr__(
            day,
            "prayer",
            PrayerSection(
                text=base_day.prayer.text,
                word_count=base_day.prayer.word_count,
                prayer_trace_map_id="ptm_missing",
                approval_status=SectionApprovalStatus.PENDING,
            ),
        )

        with pytest.raises(KeyError, match="ptm_missing"):
            validate_daily_devotional(day)
