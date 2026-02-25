"""Tests for src/generation/real_section_generator.py — Phase 011 CP1.

Proves the end-to-end artifact lifecycle:
  generator → save → orchestrator auto-resolves → validation runs → audit passes

Required behaviours:
  A. Generator creates and saves a GroundingMap with exactly 4 entries.
  B. validate_daily_devotional() auto-resolves the saved artifact and
     EXPOSITION_GROUNDING_MAP check is present and passes.
  C. audit_devotionals() reports grounding_status="pass" and
     prayer_trace_status="absent".
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.audit.artifact_audit import audit_devotionals
from src.generation.real_section_generator import DeterministicRealSectionGenerator
from src.grounding_store.store import GroundingMapStore
from src.validation.orchestrator import validate_daily_devotional


# ---------------------------------------------------------------------------
# Shared fixture: redirect GroundingMapStore to tmp_path for all tests.
# ---------------------------------------------------------------------------


@pytest.fixture()
def gen_with_store(tmp_path: Path, monkeypatch):
    """Return (generator, store) with DEFAULT_ROOT redirected to tmp_path."""
    monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", tmp_path)
    gen = DeterministicRealSectionGenerator()
    store = GroundingMapStore(tmp_path)
    return gen, store


# ---------------------------------------------------------------------------
# Test A — Artifact creation and persistence
# ---------------------------------------------------------------------------


class TestArtifactCreated:
    def test_creates_and_saves_grounding_map(self, gen_with_store):
        gen, store = gen_with_store
        day = gen.generate_day("grace", 1)

        gm_id = day.exposition.grounding_map_id
        assert gm_id, "grounding_map_id must be truthy"
        assert store.exists(gm_id), "GroundingMap must be persisted in store"

    def test_grounding_map_has_four_entries(self, gen_with_store):
        gen, store = gen_with_store
        day = gen.generate_day("grace", 1)

        gm = store.load(day.exposition.grounding_map_id)
        assert len(gm.entries) == 4

    def test_grounding_map_id_is_deterministic(self, gen_with_store):
        gen, store = gen_with_store
        day1 = gen.generate_day("grace", 1)
        day2 = gen.generate_day("grace", 1)
        assert day1.exposition.grounding_map_id == day2.exposition.grounding_map_id

    def test_different_inputs_produce_different_ids(self, gen_with_store):
        gen, store = gen_with_store
        day1 = gen.generate_day("grace", 1)
        day2 = gen.generate_day("grace", 2)
        assert day1.exposition.grounding_map_id != day2.exposition.grounding_map_id


# ---------------------------------------------------------------------------
# Test B — Orchestrator auto-resolution
# ---------------------------------------------------------------------------


class TestOrchestratorIntegration:
    def test_exposition_grounding_map_check_present(self, gen_with_store):
        gen, _store = gen_with_store
        day = gen.generate_day("grace", 1)

        assessments = validate_daily_devotional(day)
        check_ids = {a.check_id for a in assessments}
        assert "EXPOSITION_GROUNDING_MAP" in check_ids, (
            "EXPOSITION_GROUNDING_MAP check must be present when grounding_map_id is truthy"
        )

    def test_exposition_grounding_map_check_passes(self, gen_with_store):
        gen, _store = gen_with_store
        day = gen.generate_day("grace", 1)

        assessments = validate_daily_devotional(day)
        grounding_check = next(
            a for a in assessments if a.check_id == "EXPOSITION_GROUNDING_MAP"
        )
        assert grounding_check.result == "pass", (
            f"EXPOSITION_GROUNDING_MAP check failed: {grounding_check.reason_code}"
        )


# ---------------------------------------------------------------------------
# Test C — Audit layer integration
# ---------------------------------------------------------------------------


class TestAuditIntegration:
    def test_grounding_status_pass(self, gen_with_store):
        gen, _store = gen_with_store
        day = gen.generate_day("grace", 1)

        results = audit_devotionals([day])
        assert len(results) == 1
        assert results[0].grounding_status == "pass"

    def test_prayer_trace_status_absent(self, gen_with_store):
        gen, _store = gen_with_store
        day = gen.generate_day("grace", 1)

        results = audit_devotionals([day])
        assert results[0].prayer_trace_status == "absent"
