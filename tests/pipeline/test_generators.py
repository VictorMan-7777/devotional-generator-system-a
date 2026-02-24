"""Tests for src/generation/generators.py — MockSectionGenerator and FailFirstMockGenerator."""
from __future__ import annotations

import re

from src.generation.generators import FailFirstMockGenerator, MockSectionGenerator
from src.validation.orchestrator import validate_daily_devotional


class TestMockSectionGenerator:
    def _day(self, day_number: int = 1):
        return MockSectionGenerator().generate_day("grace", day_number)

    def test_produces_valid_day_via_orchestrator(self):
        day = self._day()
        failing = [a for a in validate_daily_devotional(day) if a.result == "fail"]
        assert failing == [], (
            f"Expected no failures, got: {[(a.check_id, a.reason_code) for a in failing]}"
        )

    def test_exposition_word_count_is_550(self):
        day = self._day()
        assert len(day.exposition.text.split()) == 550

    def test_exposition_no_second_person(self):
        day = self._day()
        assert not re.search(r"\b(you|your)\b", day.exposition.text, re.IGNORECASE)

    def test_prayer_word_count_is_150(self):
        day = self._day()
        assert len(day.prayer.text.split()) == 150

    def test_prayer_starts_with_father(self):
        day = self._day()
        assert day.prayer.text.startswith("Father,")

    def test_be_still_has_three_prompts(self):
        day = self._day()
        assert len(day.be_still.prompts) == 3

    def test_be_still_has_second_person_in_at_least_one_prompt(self):
        day = self._day()
        pattern = re.compile(r"\b(you|your)\b", re.IGNORECASE)
        assert any(pattern.search(p) for p in day.be_still.prompts)

    def test_quote_text_unique_per_day_number(self):
        gen = MockSectionGenerator()
        day1 = gen.generate_day("grace", 1)
        day2 = gen.generate_day("grace", 2)
        assert day1.timeless_wisdom.quote_text != day2.timeless_wisdom.quote_text

    def test_sending_prompt_is_none(self):
        assert self._day().sending_prompt is None

    def test_day7_is_none(self):
        assert self._day().day7 is None

    def test_multiple_days_all_validate_clean(self):
        gen = MockSectionGenerator()
        for n in range(1, 4):
            day = gen.generate_day("faith", n)
            failing = [a for a in validate_daily_devotional(day) if a.result == "fail"]
            assert failing == [], (
                f"Day {n}: unexpected failures: "
                f"{[(a.check_id, a.reason_code) for a in failing]}"
            )

    def test_connector_phrase_non_empty(self):
        day = self._day()
        assert day.action_steps.connector_phrase.strip() != ""


class TestFailFirstMockGenerator:
    def test_attempt_1_fails_exposition_word_count(self):
        gen = FailFirstMockGenerator()
        day = gen.generate_day("grace", 1, attempt_number=1)
        assessments = validate_daily_devotional(day)
        failing_ids = {a.check_id for a in assessments if a.result == "fail"}
        assert "EXPOSITION_WORD_COUNT" in failing_ids

    def test_attempt_1_exposition_has_100_words(self):
        gen = FailFirstMockGenerator()
        day = gen.generate_day("grace", 1, attempt_number=1)
        assert len(day.exposition.text.split()) == 100

    def test_attempt_2_passes_all_validators(self):
        gen = FailFirstMockGenerator()
        day = gen.generate_day("grace", 1, attempt_number=2)
        failing = [a for a in validate_daily_devotional(day) if a.result == "fail"]
        assert failing == [], (
            f"Attempt 2 should pass, got: {[(a.check_id, a.reason_code) for a in failing]}"
        )
