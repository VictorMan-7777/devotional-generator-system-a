"""Tests for src/validation/orchestrator.py — validate_daily_devotional().

Includes integration test using the existing SAMPLE_BOOK fixture.
"""
from __future__ import annotations

import pytest

from src.models.devotional import (
    ActionStepsSection,
    BeStillSection,
    ExpositionSection,
    PrayerSection,
)
from src.validation.orchestrator import validate_daily_devotional
from tests.fixtures.sample_devotional import SAMPLE_BOOK


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _results_by_id(assessments) -> dict[str, str]:
    """Return {check_id: result} mapping for easy assertion."""
    return {a.check_id: a.result for a in assessments}


def _check_ids(assessments) -> set[str]:
    return {a.check_id for a in assessments}


# ---------------------------------------------------------------------------
# Integration test — fixture must produce all-pass assessments
# ---------------------------------------------------------------------------

class TestIntegrationWithFixture:
    def test_all_assessments_pass_for_day_1(self):
        day = SAMPLE_BOOK.days[0]  # Day 1 — known-good fixture
        assessments = validate_daily_devotional(day)
        results = _results_by_id(assessments)

        # Every assessment must pass (no failures in the well-formed fixture).
        failing = [a for a in assessments if a.result == "fail"]
        assert failing == [], (
            f"Expected all assessments to pass, but got failures: "
            f"{[(a.check_id, a.reason_code) for a in failing]}"
        )

    def test_expected_check_ids_present_for_day_1(self):
        day = SAMPLE_BOOK.days[0]
        assessments = validate_daily_devotional(day)
        ids = _check_ids(assessments)

        # All non-optional check IDs must be present.
        assert "EXPOSITION_WORD_COUNT" in ids
        assert "EXPOSITION_VOICE" in ids
        assert "BE_STILL_PROMPT_COUNT" in ids
        assert "BE_STILL_SECOND_PERSON" in ids
        assert "ACTION_STEPS_COUNT" in ids
        assert "ACTION_STEPS_CONNECTOR_PHRASE" in ids
        assert "PRAYER_WORD_COUNT" in ids
        assert "PRAYER_TRINITY_ADDRESS" in ids

    def test_grounding_map_check_absent_when_not_provided(self):
        day = SAMPLE_BOOK.days[0]
        assessments = validate_daily_devotional(day, grounding_map=None)
        assert "EXPOSITION_GROUNDING_MAP" not in _check_ids(assessments)

    def test_prayer_trace_map_check_absent_when_not_provided(self):
        day = SAMPLE_BOOK.days[0]
        assessments = validate_daily_devotional(day, prayer_trace_map=None)
        assert "PRAYER_TRACE_MAP" not in _check_ids(assessments)

    def test_all_days_in_sample_book_pass(self):
        for day in SAMPLE_BOOK.days:
            assessments = validate_daily_devotional(day)
            failing = [a for a in assessments if a.result == "fail"]
            assert failing == [], (
                f"Day {day.day_number}: unexpected failures: "
                f"{[(a.check_id, a.reason_code) for a in failing]}"
            )


# ---------------------------------------------------------------------------
# Failure injection tests (using modified copies of day 1)
# ---------------------------------------------------------------------------

class TestFailureInjection:
    def _day_with_exposition(self, text: str):
        """Return a copy of day 1 with a custom exposition text."""
        day = SAMPLE_BOOK.days[0].model_copy(deep=True)
        object.__setattr__(
            day,
            "exposition",
            ExpositionSection(
                text=text,
                word_count=len(text.split()),
                grounding_map_id="",
            ),
        )
        return day

    def _day_with_be_still(self, prompts: list[str]):
        day = SAMPLE_BOOK.days[0].model_copy(deep=True)
        object.__setattr__(day, "be_still", BeStillSection(prompts=prompts))
        return day

    def _day_with_action_steps(self, items: list[str], connector: str):
        day = SAMPLE_BOOK.days[0].model_copy(deep=True)
        object.__setattr__(
            day,
            "action_steps",
            ActionStepsSection(items=items, connector_phrase=connector),
        )
        return day

    def _day_with_prayer(self, text: str):
        day = SAMPLE_BOOK.days[0].model_copy(deep=True)
        object.__setattr__(
            day,
            "prayer",
            PrayerSection(
                text=text,
                word_count=len(text.split()),
                prayer_trace_map_id="ptm-test",
            ),
        )
        return day

    def test_short_exposition_text_triggers_word_count_failure(self):
        # Construct exposition.text with exactly 400 words (below 500 minimum).
        short_text = " ".join(["grace"] * 400)
        day = self._day_with_exposition(short_text)
        assessments = validate_daily_devotional(day)
        results = _results_by_id(assessments)
        assert results["EXPOSITION_WORD_COUNT"] == "fail"
        failing = [a for a in assessments if a.check_id == "EXPOSITION_WORD_COUNT"]
        assert failing[0].reason_code == "EXPOSITION_WORD_COUNT_VIOLATION"

    def test_second_person_exposition_triggers_voice_failure(self):
        # Exposition with "you" — communal voice prohibition triggered.
        text = "you " + " ".join(["grace"] * 549)  # 550 words, has "you"
        day = self._day_with_exposition(text)
        assessments = validate_daily_devotional(day)
        results = _results_by_id(assessments)
        assert results["EXPOSITION_VOICE"] == "fail"

    def test_too_few_be_still_prompts_triggers_count_failure(self):
        day = self._day_with_be_still(["What is your response?"])  # 1 prompt, below 3
        assessments = validate_daily_devotional(day)
        results = _results_by_id(assessments)
        assert results["BE_STILL_PROMPT_COUNT"] == "fail"

    def test_missing_connector_phrase_triggers_action_steps_failure(self):
        day = self._day_with_action_steps(["Do one good thing today."], connector="")
        assessments = validate_daily_devotional(day)
        results = _results_by_id(assessments)
        assert results["ACTION_STEPS_CONNECTOR_PHRASE"] == "fail"

    def test_short_prayer_text_triggers_word_count_failure(self):
        # Construct prayer.text with exactly 100 words (below 120 minimum).
        short_prayer = "Father " + " ".join(["grace"] * 99)
        day = self._day_with_prayer(short_prayer)
        assessments = validate_daily_devotional(day)
        results = _results_by_id(assessments)
        assert results["PRAYER_WORD_COUNT"] == "fail"

    def test_prosperity_gospel_in_exposition_triggers_doctrinal_failure(self):
        # Inject prosperity gospel text into exposition (500 words min).
        prosperity_text = "God wants you rich. " + " ".join(["grace"] * 499)
        day = self._day_with_exposition(prosperity_text)
        assessments = validate_daily_devotional(day)
        ids_that_fail = {a.check_id for a in assessments if a.result == "fail"}
        assert "DOCTRINAL_PROSPERITY" in ids_that_fail

    def test_works_merit_in_prayer_triggers_doctrinal_failure(self):
        # Inject works-merit text into prayer.
        works_text = "Father, help us earn your love. " + " ".join(["grace"] * 130)
        day = self._day_with_prayer(works_text)
        assessments = validate_daily_devotional(day)
        ids_that_fail = {a.check_id for a in assessments if a.result == "fail"}
        assert "DOCTRINAL_WORKS_MERIT" in ids_that_fail


# ---------------------------------------------------------------------------
# Aggregation tests
# ---------------------------------------------------------------------------

class TestAggregation:
    def test_orchestrator_returns_list(self):
        day = SAMPLE_BOOK.days[0]
        result = validate_daily_devotional(day)
        assert isinstance(result, list)

    def test_orchestrator_does_not_modify_day(self):
        day = SAMPLE_BOOK.days[0]
        original_text = day.exposition.text
        validate_daily_devotional(day)
        assert day.exposition.text == original_text
