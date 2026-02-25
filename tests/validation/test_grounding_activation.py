"""Phase 008 — Controlled Grounding Activation tests.

Tests that validate_daily_devotional() auto-resolves a GroundingMap from the
canonical store when exposition.grounding_map_id is present, and preserves
existing behaviour when it is absent.

Required behaviours:
  1. No id → no exception, no EXPOSITION_GROUNDING_MAP check executed.
  2. Id present and stored → check executes and passes.
  3. Id present but missing → KeyError propagates (no silent skip).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.generation.generators import MockSectionGenerator
from src.grounding_store.store import GroundingMapStore
from src.interfaces.rag import RetrievedExcerpt
from src.models.devotional import ExpositionSection, SectionApprovalStatus
from src.rag.grounding import GroundingMapBuilder
from src.validation.orchestrator import validate_daily_devotional


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
        1: [_make_excerpt("Declaration paragraph excerpt.")],
        2: [_make_excerpt("Context paragraph excerpt.")],
        3: [_make_excerpt("Theological paragraph excerpt.")],
        4: [_make_excerpt("Bridge paragraph excerpt.")],
    }


# ---------------------------------------------------------------------------
# Test 1 — No id (baseline): behaviour unchanged
# ---------------------------------------------------------------------------


class TestNoId:
    def test_no_exception_when_grounding_map_id_is_empty(self):
        """Empty grounding_map_id → auto-resolution skipped → no exception."""
        day = MockSectionGenerator().generate_day("grace", 1)
        # grounding_map_id is "" (falsy) — auto-resolution must not fire.
        assert day.exposition.grounding_map_id == ""
        assessments = validate_daily_devotional(day)
        # Must complete without error.
        assert isinstance(assessments, list)

    def test_grounding_check_absent_when_no_id(self):
        """No id → EXPOSITION_GROUNDING_MAP check is not emitted."""
        day = MockSectionGenerator().generate_day("grace", 1)
        assessments = validate_daily_devotional(day)
        check_ids = {a.check_id for a in assessments}
        assert "EXPOSITION_GROUNDING_MAP" not in check_ids


# ---------------------------------------------------------------------------
# Test 2 — Id present and stored: check executes and passes
# ---------------------------------------------------------------------------


class TestIdPresentAndStored:
    def test_grounding_check_executes_and_passes(
        self, tmp_path: Path, monkeypatch
    ):
        """Auto-resolution loads the stored map; EXPOSITION_GROUNDING_MAP passes."""
        # Build and save a valid GroundingMap.
        gm = GroundingMapBuilder().build("expo-phase008-test", _four_paragraph_excerpts())
        store = GroundingMapStore(tmp_path)
        store.save(gm)

        # Redirect the canonical store to tmp_path.
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", tmp_path)

        # Build a day whose exposition carries the saved map's id.
        base_day = MockSectionGenerator().generate_day("grace", 1)
        day = base_day.model_copy(deep=True)
        object.__setattr__(
            day,
            "exposition",
            ExpositionSection(
                text=base_day.exposition.text,
                word_count=base_day.exposition.word_count,
                grounding_map_id=gm.id,
                approval_status=SectionApprovalStatus.PENDING,
            ),
        )

        # Call without explicit grounding_map — auto-resolution fires.
        assessments = validate_daily_devotional(day)

        check_ids = {a.check_id for a in assessments}
        assert "EXPOSITION_GROUNDING_MAP" in check_ids, (
            "EXPOSITION_GROUNDING_MAP check was not executed — auto-resolution failed"
        )

        gm_check = next(a for a in assessments if a.check_id == "EXPOSITION_GROUNDING_MAP")
        assert gm_check.result == "pass", (
            f"EXPOSITION_GROUNDING_MAP check failed: {gm_check.reason_code}"
        )


# ---------------------------------------------------------------------------
# Test 3 — Id present but missing: KeyError propagates
# ---------------------------------------------------------------------------


class TestIdPresentButMissing:
    def test_missing_artifact_raises_key_error(self, tmp_path: Path, monkeypatch):
        """Missing artifact → KeyError; id appears in error message."""
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", tmp_path)

        base_day = MockSectionGenerator().generate_day("grace", 1)
        day = base_day.model_copy(deep=True)
        object.__setattr__(
            day,
            "exposition",
            ExpositionSection(
                text=base_day.exposition.text,
                word_count=base_day.exposition.word_count,
                grounding_map_id="gm_missing",
                approval_status=SectionApprovalStatus.PENDING,
            ),
        )

        with pytest.raises(KeyError, match="gm_missing"):
            validate_daily_devotional(day)
