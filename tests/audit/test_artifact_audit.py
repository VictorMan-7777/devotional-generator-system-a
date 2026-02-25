"""Tests for src/audit/artifact_audit.py — audit_devotionals().

Required behaviours:
  1. No IDs → both statuses "absent"
  2. Valid grounding only → grounding "pass", prayer_trace "absent"
  3. Missing grounding artifact → grounding "missing"
  4. Invalid grounding artifact (corrupt JSON) → grounding "invalid"
  5. Valid prayer trace only → grounding "absent", prayer_trace "pass"
  6. Missing prayer trace artifact → prayer_trace "missing"
  7. Deterministic ordering by devotional_id ascending
  8. Audit never raises (mixed missing/invalid)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.audit.artifact_audit import ArtifactAuditResult, audit_devotionals
from src.generation.generators import MockSectionGenerator
from src.grounding_store.store import GroundingMapStore
from src.interfaces.rag import RetrievedExcerpt
from src.models.artifacts import PrayerTraceMap, PrayerTraceMapEntry
from src.models.devotional import (
    ExpositionSection,
    PrayerSection,
    SectionApprovalStatus,
)
from src.prayer_trace_store.store import PrayerTraceMapStore
from src.rag.grounding import GroundingMapBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_excerpt(text: str) -> RetrievedExcerpt:
    return RetrievedExcerpt(
        text=text,
        source_title="Source",
        author="Author",
        source_type="commentary",
    )


def _four_paragraph_excerpts() -> dict:
    return {
        1: [_make_excerpt("Declaration: God's grace abounds.")],
        2: [_make_excerpt("Context: Historical background.")],
        3: [_make_excerpt("Theological: The nature of grace.")],
        4: [_make_excerpt("Bridge: Application to daily life.")],
    }


def _valid_trace_map(ptm_id: str = "ptm-audit-001") -> PrayerTraceMap:
    return PrayerTraceMap(
        id=ptm_id,
        prayer_id="prayer-audit-test",
        entries=[
            PrayerTraceMapEntry(
                element_text="Father, thank you for grace.",
                source_type="scripture",
                source_reference="Romans 8:28",
            ),
            PrayerTraceMapEntry(
                element_text="Guide us in your truth.",
                source_type="exposition",
                source_reference="Paragraph 1.",
            ),
        ],
    )


def _day_with_ids(
    day_number: int = 1,
    grounding_map_id: str = "",
    prayer_trace_map_id: str = "",
):
    base = MockSectionGenerator().generate_day("grace", day_number)
    day = base.model_copy(deep=True)
    object.__setattr__(
        day,
        "exposition",
        ExpositionSection(
            text=base.exposition.text,
            word_count=base.exposition.word_count,
            grounding_map_id=grounding_map_id,
            approval_status=SectionApprovalStatus.PENDING,
        ),
    )
    object.__setattr__(
        day,
        "prayer",
        PrayerSection(
            text=base.prayer.text,
            word_count=base.prayer.word_count,
            prayer_trace_map_id=prayer_trace_map_id,
            approval_status=SectionApprovalStatus.PENDING,
        ),
    )
    return day


def _patch_stores(monkeypatch, tmp_path: Path):
    """Redirect both stores to tmp_path subdirectories."""
    gm_dir = tmp_path / "gm"
    ptm_dir = tmp_path / "ptm"
    gm_dir.mkdir()
    ptm_dir.mkdir()
    monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", gm_dir)
    monkeypatch.setattr(PrayerTraceMapStore, "DEFAULT_ROOT", ptm_dir)
    return gm_dir, ptm_dir


# ---------------------------------------------------------------------------
# Test 1 — No IDs: both statuses "absent"
# ---------------------------------------------------------------------------


class TestNoIds:
    def test_both_absent_when_no_ids(self):
        day = _day_with_ids(grounding_map_id="", prayer_trace_map_id="")
        results = audit_devotionals([day])
        assert len(results) == 1
        assert results[0].grounding_status == "absent"
        assert results[0].prayer_trace_status == "absent"

    def test_returns_list(self):
        day = _day_with_ids()
        results = audit_devotionals([day])
        assert isinstance(results, list)
        assert isinstance(results[0], ArtifactAuditResult)


# ---------------------------------------------------------------------------
# Test 2 — Valid grounding only
# ---------------------------------------------------------------------------


class TestValidGroundingOnly:
    def test_grounding_pass_prayer_absent(self, tmp_path: Path, monkeypatch):
        gm_dir, _ptm_dir = _patch_stores(monkeypatch, tmp_path)

        gm = GroundingMapBuilder().build("expo-audit-001", _four_paragraph_excerpts())
        GroundingMapStore(gm_dir).save(gm)

        day = _day_with_ids(grounding_map_id=gm.id, prayer_trace_map_id="")
        results = audit_devotionals([day])

        assert results[0].grounding_status == "pass"
        assert results[0].prayer_trace_status == "absent"


# ---------------------------------------------------------------------------
# Test 3 — Missing grounding artifact
# ---------------------------------------------------------------------------


class TestMissingGrounding:
    def test_grounding_missing(self, tmp_path: Path, monkeypatch):
        _patch_stores(monkeypatch, tmp_path)

        day = _day_with_ids(grounding_map_id="gm-does-not-exist")
        results = audit_devotionals([day])

        assert results[0].grounding_status == "missing"
        assert any("gm-does-not-exist" in d for d in results[0].details)


# ---------------------------------------------------------------------------
# Test 4 — Invalid grounding artifact (corrupt JSON → ValidationError)
# ---------------------------------------------------------------------------


class TestInvalidGrounding:
    def test_grounding_invalid_corrupt_file(self, tmp_path: Path, monkeypatch):
        gm_dir, _ptm_dir = _patch_stores(monkeypatch, tmp_path)

        # Write a file that is valid JSON but fails GroundingMap Pydantic validation.
        corrupt_id = "gm-corrupt-001"
        (gm_dir / f"{corrupt_id}.json").write_text("{}", encoding="utf-8")

        day = _day_with_ids(grounding_map_id=corrupt_id)
        results = audit_devotionals([day])

        assert results[0].grounding_status == "invalid"


# ---------------------------------------------------------------------------
# Test 5 — Valid prayer trace only
# ---------------------------------------------------------------------------


class TestValidPrayerTraceOnly:
    def test_prayer_trace_pass_grounding_absent(self, tmp_path: Path, monkeypatch):
        _gm_dir, ptm_dir = _patch_stores(monkeypatch, tmp_path)

        ptm = _valid_trace_map("ptm-audit-001")
        PrayerTraceMapStore(ptm_dir).save(ptm)

        day = _day_with_ids(grounding_map_id="", prayer_trace_map_id=ptm.id)
        results = audit_devotionals([day])

        assert results[0].grounding_status == "absent"
        assert results[0].prayer_trace_status == "pass"


# ---------------------------------------------------------------------------
# Test 6 — Missing prayer trace artifact
# ---------------------------------------------------------------------------


class TestMissingPrayerTrace:
    def test_prayer_trace_missing(self, tmp_path: Path, monkeypatch):
        _patch_stores(monkeypatch, tmp_path)

        day = _day_with_ids(prayer_trace_map_id="ptm-does-not-exist")
        results = audit_devotionals([day])

        assert results[0].prayer_trace_status == "missing"
        assert any("ptm-does-not-exist" in d for d in results[0].details)


# ---------------------------------------------------------------------------
# Test 7 — Deterministic ordering (sorted by devotional_id ascending)
# ---------------------------------------------------------------------------


class TestDeterministicOrdering:
    def test_results_sorted_by_devotional_id(self):
        # Provide day_number=2 first, day_number=1 second.
        day2 = _day_with_ids(day_number=2)
        day1 = _day_with_ids(day_number=1)

        results = audit_devotionals([day2, day1])

        assert len(results) == 2
        assert results[0].devotional_id == "day-1"
        assert results[1].devotional_id == "day-2"

    def test_ordering_is_stable_when_already_sorted(self):
        day1 = _day_with_ids(day_number=1)
        day3 = _day_with_ids(day_number=3)

        results = audit_devotionals([day1, day3])

        assert results[0].devotional_id == "day-1"
        assert results[1].devotional_id == "day-3"


# ---------------------------------------------------------------------------
# Test 8 — Audit never raises (mixed missing/invalid)
# ---------------------------------------------------------------------------


class TestNeverRaises:
    def test_mixed_missing_and_invalid_does_not_raise(
        self, tmp_path: Path, monkeypatch
    ):
        gm_dir, ptm_dir = _patch_stores(monkeypatch, tmp_path)

        # One day: missing grounding, valid prayer trace.
        ptm = _valid_trace_map("ptm-mixed-001")
        PrayerTraceMapStore(ptm_dir).save(ptm)
        day1 = _day_with_ids(
            day_number=1,
            grounding_map_id="gm-missing",
            prayer_trace_map_id=ptm.id,
        )

        # Another day: corrupt grounding, missing prayer trace.
        corrupt_id = "gm-corrupt-mix"
        (gm_dir / f"{corrupt_id}.json").write_text("{}", encoding="utf-8")
        day2 = _day_with_ids(
            day_number=2,
            grounding_map_id=corrupt_id,
            prayer_trace_map_id="ptm-missing",
        )

        # Must not raise.
        results = audit_devotionals([day1, day2])

        assert len(results) == 2
        r1 = next(r for r in results if r.devotional_id == "day-1")
        r2 = next(r for r in results if r.devotional_id == "day-2")

        assert r1.grounding_status == "missing"
        assert r1.prayer_trace_status == "pass"
        assert r2.grounding_status == "invalid"
        assert r2.prayer_trace_status == "missing"
