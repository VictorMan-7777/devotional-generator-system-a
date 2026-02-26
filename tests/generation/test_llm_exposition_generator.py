"""Tests for src/generation/llm_exposition_generator.py — Phase 012 CP1.

Proves the end-to-end LLM exposition lifecycle:
  LLMExpositionGenerator -> saves GroundingMap -> DailyDevotional carries id ->
  validate_daily_devotional(day) auto-resolves -> grounding validation passes ->
  audit_devotionals([day]) reports grounding_status="pass"

Required behaviours:
  A. Generator saves a GroundingMap with a deterministic id and exactly 4 entries.
  B. validate_daily_devotional() auto-resolves the saved artifact and
     EXPOSITION_GROUNDING_MAP check is present and passes.
  C. audit_devotionals() reports grounding_status="pass" and
     prayer_trace_status="absent".
  D. LLM is called exactly once per generate_exposition() invocation.

All tests are deterministic — no network calls, no real LLM.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.audit.artifact_audit import audit_devotionals
from src.generation.generators import MockSectionGenerator
from src.generation.llm_exposition_generator import LLMExpositionGenerator
from src.grounding_store.id_policy import create_grounding_map_id
from src.grounding_store.store import GroundingMapStore
from src.models.devotional import ExpositionSection, SectionApprovalStatus
from src.validation.orchestrator import validate_daily_devotional


# ---------------------------------------------------------------------------
# FakeLLMClient
# ---------------------------------------------------------------------------

# 4 explicit paragraphs labelled declaration / context / theological / bridge.
# Each paragraph: 1 label word + 136 filler words = 137 words.
# Total: 4 × 137 = 548 words — within the 500–700 word count requirement.
# No "you" or "your" — passes EXPOSITION_VOICE check.
# No prosperity/works-merit patterns — passes doctrinal guardrails.
_FAKE_LLM_TEXT = "\n\n".join(
    [
        "declaration " + " ".join(["grace"] * 136),
        "context " + " ".join(["mercy"] * 136),
        "theological " + " ".join(["faith"] * 136),
        "bridge " + " ".join(["hope"] * 136),
    ]
)


class FakeLLMClient:
    """Deterministic LLM stub. Tracks call count; returns fixed exposition text."""

    def __init__(self) -> None:
        self.call_count: int = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        return _FAKE_LLM_TEXT


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def gen_and_store(tmp_path: Path, monkeypatch):
    """Return (generator, store, fake_llm) with DEFAULT_ROOT redirected to tmp_path.

    A single monkeypatch covers all three seam points:
      - LLMExpositionGenerator._store (reads DEFAULT_ROOT at call-time)
      - orchestrator auto-resolution (reads DEFAULT_ROOT at call-time)
      - audit_devotionals _audit_grounding (reads DEFAULT_ROOT at call-time)
    """
    monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", tmp_path)
    fake_llm = FakeLLMClient()
    gen = LLMExpositionGenerator(llm=fake_llm)
    store = GroundingMapStore(tmp_path)
    return gen, store, fake_llm


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _day_from_exposition(exposition: ExpositionSection, day_number: int = 1):
    """Build a full DailyDevotional by replacing the exposition on a base day.

    Uses MockSectionGenerator for all sections except exposition — those
    sections are already validated to pass all checks (word count, voice,
    doctrinal, prayer trinity address, etc.).
    """
    base = MockSectionGenerator().generate_day("grace", day_number)
    day = base.model_copy(deep=True)
    object.__setattr__(
        day,
        "exposition",
        ExpositionSection(
            text=exposition.text,
            word_count=exposition.word_count,
            grounding_map_id=exposition.grounding_map_id,
            approval_status=SectionApprovalStatus.PENDING,
        ),
    )
    return day


# ---------------------------------------------------------------------------
# Test A — GroundingMap persisted with deterministic id
# ---------------------------------------------------------------------------


class TestGroundingMapPersisted:
    def test_grounding_map_id_matches_id_policy(self, gen_and_store):
        gen, store, _llm = gen_and_store
        exposition = gen.generate_exposition("expo-grace-day1", "grace", "Romans 8:28")

        expected_id = create_grounding_map_id("expo-grace-day1")
        assert exposition.grounding_map_id == expected_id, (
            "grounding_map_id must equal create_grounding_map_id(exposition_id)"
        )

    def test_grounding_map_file_exists_in_store(self, gen_and_store):
        gen, store, _llm = gen_and_store
        exposition = gen.generate_exposition("expo-grace-day1", "grace", "Romans 8:28")

        assert store.exists(exposition.grounding_map_id), (
            "GroundingMap must be persisted to the store before returning"
        )

    def test_grounding_map_has_four_entries(self, gen_and_store):
        gen, store, _llm = gen_and_store
        exposition = gen.generate_exposition("expo-grace-day1", "grace", "Romans 8:28")

        gm = store.load(exposition.grounding_map_id)
        assert len(gm.entries) == 4, (
            "GroundingMap must have exactly 4 entries (one per paragraph)"
        )


# ---------------------------------------------------------------------------
# Test B — validate_daily_devotional auto-resolves grounding
# ---------------------------------------------------------------------------


class TestOrchestratorAutoResolution:
    def test_prayer_trace_map_id_is_falsy(self, gen_and_store):
        """Precondition: prayer remains deterministic — prayer_trace_map_id must be falsy."""
        gen, _store, _llm = gen_and_store
        exposition = gen.generate_exposition("expo-grace-day1", "grace", "Romans 8:28")
        day = _day_from_exposition(exposition)

        assert not day.prayer.prayer_trace_map_id, (
            "prayer_trace_map_id must remain falsy in Phase 012"
        )

    def test_exposition_grounding_map_check_present(self, gen_and_store):
        gen, _store, _llm = gen_and_store
        exposition = gen.generate_exposition("expo-grace-day1", "grace", "Romans 8:28")
        day = _day_from_exposition(exposition)

        assessments = validate_daily_devotional(day)
        check_ids = {a.check_id for a in assessments}

        assert "EXPOSITION_GROUNDING_MAP" in check_ids, (
            "EXPOSITION_GROUNDING_MAP must be present when grounding_map_id is truthy"
        )

    def test_exposition_grounding_map_check_passes(self, gen_and_store):
        gen, _store, _llm = gen_and_store
        exposition = gen.generate_exposition("expo-grace-day1", "grace", "Romans 8:28")
        day = _day_from_exposition(exposition)

        assessments = validate_daily_devotional(day)
        gm_check = next(
            a for a in assessments if a.check_id == "EXPOSITION_GROUNDING_MAP"
        )

        assert gm_check.result == "pass", (
            f"EXPOSITION_GROUNDING_MAP check failed: {gm_check.reason_code}"
        )


# ---------------------------------------------------------------------------
# Test C — audit_devotionals reports grounding pass / prayer absent
# ---------------------------------------------------------------------------


class TestAuditResult:
    def test_grounding_status_pass(self, gen_and_store):
        gen, _store, _llm = gen_and_store
        exposition = gen.generate_exposition("expo-grace-day1", "grace", "Romans 8:28")
        day = _day_from_exposition(exposition)

        results = audit_devotionals([day])

        assert len(results) == 1
        assert results[0].grounding_status == "pass"

    def test_prayer_trace_status_absent(self, gen_and_store):
        gen, _store, _llm = gen_and_store
        exposition = gen.generate_exposition("expo-grace-day1", "grace", "Romans 8:28")
        day = _day_from_exposition(exposition)

        results = audit_devotionals([day])

        assert results[0].prayer_trace_status == "absent"


# ---------------------------------------------------------------------------
# Test D — LLM called exactly once
# ---------------------------------------------------------------------------


class TestLLMCallCount:
    def test_llm_called_exactly_once(self, gen_and_store):
        gen, _store, fake_llm = gen_and_store
        gen.generate_exposition("expo-grace-day1", "grace", "Romans 8:28")

        assert fake_llm.call_count == 1, (
            f"LLM must be called exactly once; got {fake_llm.call_count}"
        )

    def test_second_call_increments_count(self, gen_and_store):
        """Each generate_exposition() call is independent and calls LLM once."""
        gen, _store, fake_llm = gen_and_store
        gen.generate_exposition("expo-grace-day1", "grace", "Romans 8:28")
        gen.generate_exposition("expo-grace-day2", "grace", "Romans 8:29")

        assert fake_llm.call_count == 2
