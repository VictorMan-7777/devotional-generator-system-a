"""Tests for src/generation/llm_prayer_generator.py — Phase 013 CP1.

Proves the end-to-end LLM prayer lifecycle:
  LLMPrayerGenerator -> saves PrayerTraceMap -> DailyDevotional carries id ->
  validate_daily_devotional(day) auto-resolves -> prayer validation passes ->
  audit_devotionals([day]) reports prayer_trace_status="pass"

Also proves the combined lifecycle:
  LLMExpositionGenerator + LLMPrayerGenerator -> both artifacts persisted ->
  validate_daily_devotional passes both grounding and prayer trace checks ->
  audit_devotionals reports both statuses "pass"

Required behaviours:
  A. Generator saves a PrayerTraceMap with a deterministic id and valid source types.
  B. validate_daily_devotional() auto-resolves the saved artifact and
     PRAYER_TRACE_MAP check is present and passes.
  C. audit_devotionals() reports prayer_trace_status="pass" and
     grounding_status="pass" (Phase 012 seam unchanged).
  D. LLM is called exactly once per generate_prayer() invocation.

All tests are deterministic — no network calls, no real LLM.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.audit.artifact_audit import audit_devotionals
from src.generation.generators import MockSectionGenerator
from src.generation.llm_exposition_generator import LLMExpositionGenerator
from src.generation.llm_prayer_generator import LLMPrayerGenerator
from src.grounding_store.store import GroundingMapStore
from src.prayer_trace_store.id_policy import create_prayer_trace_map_id
from src.prayer_trace_store.store import PrayerTraceMapStore
from src.validation.orchestrator import validate_daily_devotional


# ---------------------------------------------------------------------------
# FakePrayerLLM
# ---------------------------------------------------------------------------

# 6 lines joined by "\n" (no blank lines between).
# Each line is one prayer element; split("\n") + filter produces exactly 6 elements.
#
# Line 1: contains "8:28"      → source_type="scripture"
# Line 2: contains "exposition" → source_type="exposition"
# Line 3: no digit:digit, no "exposition" → source_type="be_still"
# Line 4: contains "46:10"     → source_type="scripture"
# Line 5: contains "exposition" → source_type="exposition"
# Line 6: no digit:digit, no "exposition" → source_type="be_still"
#
# Word count: 162 words (within 120–200 validator range).
# Trinity names present: Father, Lord, Holy Spirit, God, Jesus, Spirit.
_FAKE_PRAYER_TEXT = "\n".join([
    "Father, we anchor our prayer in Romans 8:28, trusting that all things work together for the good of those who love you and are called according to your purpose.",
    "Lord, as this exposition of your word has illuminated the depths of your grace, let that same truth transform the way we see and respond to your creation.",
    "Holy Spirit, in this stillness we open our hearts to receive whatever you have prepared for us in this moment of quiet surrender and trust.",
    "God, your promise in Psalm 46:10 calls us to be still and know, and so we cease our striving and rest in the certainty of your sovereign love.",
    "Jesus, as this exposition has shown us your boundless mercy, we pray that mercy would flow through us to those around us who are weary and burdened.",
    "Spirit, guide us as we carry this stillness with us through the day, remembering that your presence never leaves and your peace surpasses all understanding.",
])


class FakePrayerLLM:
    """Deterministic LLM stub for prayer generation. Tracks call count."""

    def __init__(self) -> None:
        self.call_count: int = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        return _FAKE_PRAYER_TEXT


# ---------------------------------------------------------------------------
# FakeExpositionLLM
# ---------------------------------------------------------------------------

# 4 explicit paragraphs labelled declaration / context / theological / bridge.
# Each paragraph: 1 label word + 136 filler words = 137 words.
# Total: 4 × 137 = 548 words — within the 500–700 word count requirement.
# No "you" or "your" — passes EXPOSITION_VOICE check.
_FAKE_EXPOSITION_TEXT = "\n\n".join([
    "declaration " + " ".join(["grace"] * 136),
    "context " + " ".join(["mercy"] * 136),
    "theological " + " ".join(["faith"] * 136),
    "bridge " + " ".join(["hope"] * 136),
])


class FakeExpositionLLM:
    """Deterministic LLM stub for exposition generation."""

    def generate(self, prompt: str) -> str:
        return _FAKE_EXPOSITION_TEXT


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def prayer_gen_and_store(tmp_path: Path, monkeypatch):
    """Return (generator, store, fake_llm) with DEFAULT_ROOT redirected to tmp_path.

    Single monkeypatch covers all three PrayerTraceMapStore seam points:
      - LLMPrayerGenerator._store (reads DEFAULT_ROOT at call-time)
      - orchestrator auto-resolution (reads DEFAULT_ROOT at call-time)
      - audit_devotionals _audit_prayer_trace (reads DEFAULT_ROOT at call-time)
    """
    monkeypatch.setattr(PrayerTraceMapStore, "DEFAULT_ROOT", tmp_path)
    fake_llm = FakePrayerLLM()
    gen = LLMPrayerGenerator(llm=fake_llm)
    store = PrayerTraceMapStore(tmp_path)
    return gen, store, fake_llm


@pytest.fixture()
def combined_setup(tmp_path: Path, monkeypatch):
    """Return (expo_gen, prayer_gen) with separate tmp dirs for each store.

    Both DEFAULT_ROOT class attributes are monkeypatched simultaneously.
    A single validate_daily_devotional() call will auto-resolve both artifacts.
    """
    gm_dir = tmp_path / "gm"
    ptm_dir = tmp_path / "ptm"
    gm_dir.mkdir()
    ptm_dir.mkdir()
    monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", gm_dir)
    monkeypatch.setattr(PrayerTraceMapStore, "DEFAULT_ROOT", ptm_dir)
    expo_gen = LLMExpositionGenerator(llm=FakeExpositionLLM())
    prayer_gen = LLMPrayerGenerator(llm=FakePrayerLLM())
    return expo_gen, prayer_gen


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _full_day(expo_gen, prayer_gen, day_number: int = 1):
    """Build a full DailyDevotional with both LLM-generated sections.

    Uses MockSectionGenerator as the base (all other sections pass validators),
    then replaces exposition and prayer with the LLM-generated versions.
    """
    exposition = expo_gen.generate_exposition(f"expo-grace-day{day_number}", "grace", "Romans 8:28")
    prayer = prayer_gen.generate_prayer(
        prayer_id=f"prayer-grace-day{day_number}",
        topic="grace",
        passage_reference="Romans 8:28",
        exposition_text=exposition.text,
        be_still_prompts=["Sit in silence.", "What is stirring?", "Rest now."],
    )
    base = MockSectionGenerator().generate_day("grace", day_number)
    day = base.model_copy(deep=True)
    object.__setattr__(day, "exposition", exposition)
    object.__setattr__(day, "prayer", prayer)
    return day


# ---------------------------------------------------------------------------
# Test A — PrayerTraceMap persisted with deterministic id
# ---------------------------------------------------------------------------


class TestPrayerTraceMapPersisted:
    def test_prayer_trace_map_id_matches_id_policy(self, prayer_gen_and_store):
        gen, store, _llm = prayer_gen_and_store
        prayer = gen.generate_prayer(
            prayer_id="prayer-grace-day1",
            topic="grace",
            passage_reference="Romans 8:28",
            exposition_text="Some exposition text here.",
            be_still_prompts=["Sit in silence."],
        )

        expected_id = create_prayer_trace_map_id("prayer-grace-day1")
        assert prayer.prayer_trace_map_id == expected_id, (
            "prayer_trace_map_id must equal create_prayer_trace_map_id(prayer_id)"
        )

    def test_prayer_trace_map_file_exists(self, prayer_gen_and_store):
        gen, store, _llm = prayer_gen_and_store
        prayer = gen.generate_prayer(
            prayer_id="prayer-grace-day1",
            topic="grace",
            passage_reference="Romans 8:28",
            exposition_text="Some exposition text here.",
            be_still_prompts=["Sit in silence."],
        )

        assert store.exists(prayer.prayer_trace_map_id), (
            "PrayerTraceMap must be persisted to the store before returning"
        )

    def test_entries_have_valid_source_types(self, prayer_gen_and_store):
        gen, store, _llm = prayer_gen_and_store
        prayer = gen.generate_prayer(
            prayer_id="prayer-grace-day1",
            topic="grace",
            passage_reference="Romans 8:28",
            exposition_text="Some exposition text here.",
            be_still_prompts=["Sit in silence."],
        )

        ptm = store.load(prayer.prayer_trace_map_id)
        valid_types = {"scripture", "exposition", "be_still"}
        for entry in ptm.entries:
            assert entry.source_type in valid_types, (
                f"Entry has invalid source_type: {entry.source_type!r}"
            )

    def test_entry_count_matches_element_count(self, prayer_gen_and_store):
        gen, store, _llm = prayer_gen_and_store
        prayer = gen.generate_prayer(
            prayer_id="prayer-grace-day1",
            topic="grace",
            passage_reference="Romans 8:28",
            exposition_text="Some exposition text here.",
            be_still_prompts=["Sit in silence."],
        )

        ptm = store.load(prayer.prayer_trace_map_id)
        assert len(ptm.entries) == 6, (
            f"Expected 6 entries from FakePrayerLLM; got {len(ptm.entries)}"
        )


# ---------------------------------------------------------------------------
# Test B — validate_daily_devotional auto-resolves prayer trace
# ---------------------------------------------------------------------------


class TestOrchestratorAutoResolution:
    def test_prayer_trace_check_present(self, combined_setup):
        expo_gen, prayer_gen = combined_setup
        day = _full_day(expo_gen, prayer_gen)

        assessments = validate_daily_devotional(day)
        check_ids = {a.check_id for a in assessments}

        assert "PRAYER_TRACE_MAP" in check_ids, (
            "PRAYER_TRACE_MAP must be present when prayer_trace_map_id is truthy"
        )

    def test_prayer_trace_check_passes(self, combined_setup):
        expo_gen, prayer_gen = combined_setup
        day = _full_day(expo_gen, prayer_gen)

        assessments = validate_daily_devotional(day)
        ptm_check = next(
            a for a in assessments if a.check_id == "PRAYER_TRACE_MAP"
        )

        assert ptm_check.result == "pass", (
            f"PRAYER_TRACE_MAP check failed: {ptm_check.reason_code}"
        )

    def test_grounding_map_check_still_passes(self, combined_setup):
        expo_gen, prayer_gen = combined_setup
        day = _full_day(expo_gen, prayer_gen)

        assessments = validate_daily_devotional(day)
        gm_check = next(
            a for a in assessments if a.check_id == "EXPOSITION_GROUNDING_MAP"
        )

        assert gm_check.result == "pass", (
            f"EXPOSITION_GROUNDING_MAP check failed: {gm_check.reason_code}"
        )


# ---------------------------------------------------------------------------
# Test C — audit_devotionals reports both pass
# ---------------------------------------------------------------------------


class TestAuditResult:
    def test_prayer_trace_status_pass(self, combined_setup):
        expo_gen, prayer_gen = combined_setup
        day = _full_day(expo_gen, prayer_gen)

        results = audit_devotionals([day])

        assert len(results) == 1
        assert results[0].prayer_trace_status == "pass"

    def test_grounding_status_still_pass(self, combined_setup):
        expo_gen, prayer_gen = combined_setup
        day = _full_day(expo_gen, prayer_gen)

        results = audit_devotionals([day])

        assert results[0].grounding_status == "pass"


# ---------------------------------------------------------------------------
# Test D — LLM called exactly once
# ---------------------------------------------------------------------------


class TestLLMCallCount:
    def test_llm_called_exactly_once(self, prayer_gen_and_store):
        gen, _store, fake_llm = prayer_gen_and_store
        gen.generate_prayer(
            prayer_id="prayer-grace-day1",
            topic="grace",
            passage_reference="Romans 8:28",
            exposition_text="Some exposition text here.",
            be_still_prompts=["Sit in silence."],
        )

        assert fake_llm.call_count == 1, (
            f"LLM must be called exactly once; got {fake_llm.call_count}"
        )

    def test_second_call_increments(self, prayer_gen_and_store):
        """Each generate_prayer() call is independent and calls LLM once."""
        gen, _store, fake_llm = prayer_gen_and_store
        gen.generate_prayer(
            prayer_id="prayer-grace-day1",
            topic="grace",
            passage_reference="Romans 8:28",
            exposition_text="Some text.",
            be_still_prompts=["Sit."],
        )
        gen.generate_prayer(
            prayer_id="prayer-grace-day2",
            topic="grace",
            passage_reference="Romans 8:29",
            exposition_text="More text.",
            be_still_prompts=["Rest."],
        )

        assert fake_llm.call_count == 2
