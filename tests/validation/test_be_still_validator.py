"""Tests for src/validation/be_still.py — FR-75 Be Still validator."""
import pytest

from src.models.devotional import BeStillSection
from src.validation.be_still import validate_be_still


def _result(results, check_id: str) -> str:
    for a in results:
        if a.check_id == check_id:
            return a.result
    raise KeyError(check_id)


_SECOND_PERSON_PROMPT = "What has God placed on your heart today?"
_IMPERATIVE_PROMPT = "Sit quietly before the Lord for two minutes."  # no you/your


class TestPromptCount:
    def test_three_prompts_passes(self):
        section = BeStillSection(prompts=[_SECOND_PERSON_PROMPT] * 3)
        assert _result(validate_be_still(section), "BE_STILL_PROMPT_COUNT") == "pass"

    def test_five_prompts_passes(self):
        section = BeStillSection(prompts=[_SECOND_PERSON_PROMPT] * 5)
        assert _result(validate_be_still(section), "BE_STILL_PROMPT_COUNT") == "pass"

    def test_four_prompts_passes(self):
        section = BeStillSection(prompts=[_SECOND_PERSON_PROMPT] * 4)
        assert _result(validate_be_still(section), "BE_STILL_PROMPT_COUNT") == "pass"

    def test_two_prompts_fails(self):
        section = BeStillSection(prompts=[_SECOND_PERSON_PROMPT] * 2)
        result = _result(validate_be_still(section), "BE_STILL_PROMPT_COUNT")
        assert result == "fail"
        assessment = next(
            a for a in validate_be_still(section) if a.check_id == "BE_STILL_PROMPT_COUNT"
        )
        assert assessment.reason_code == "BE_STILL_PROMPT_COUNT_VIOLATION"

    def test_six_prompts_fails(self):
        section = BeStillSection(prompts=[_SECOND_PERSON_PROMPT] * 6)
        assert _result(validate_be_still(section), "BE_STILL_PROMPT_COUNT") == "fail"

    def test_zero_prompts_fails(self):
        section = BeStillSection(prompts=[])
        assert _result(validate_be_still(section), "BE_STILL_PROMPT_COUNT") == "fail"


class TestSecondPerson:
    def test_at_least_one_you_passes(self):
        section = BeStillSection(
            prompts=[
                _IMPERATIVE_PROMPT,
                _SECOND_PERSON_PROMPT,  # has "your"
                _IMPERATIVE_PROMPT,
            ]
        )
        assert _result(validate_be_still(section), "BE_STILL_SECOND_PERSON") == "pass"

    def test_all_your_passes(self):
        section = BeStillSection(
            prompts=[
                "What is your response to what you just read?",
                "How does your understanding of grace change here?",
                "Where do you sense God's invitation today?",
            ]
        )
        assert _result(validate_be_still(section), "BE_STILL_SECOND_PERSON") == "pass"

    def test_no_you_or_your_fails(self):
        section = BeStillSection(
            prompts=[
                "Sit in silence for two minutes.",
                "Breathe slowly and release tension.",
                "Offer gratitude in stillness.",
            ]
        )
        result = _result(validate_be_still(section), "BE_STILL_SECOND_PERSON")
        assert result == "fail"
        assessment = next(
            a for a in validate_be_still(section) if a.check_id == "BE_STILL_SECOND_PERSON"
        )
        assert assessment.reason_code == "BE_STILL_SECOND_PERSON_ABSENT"

    def test_you_case_insensitive(self):
        section = BeStillSection(
            prompts=["What does YOUR heart say?", "Breathe.", "Rest."]
        )
        assert _result(validate_be_still(section), "BE_STILL_SECOND_PERSON") == "pass"

    def test_fixture_style_passes(self):
        # Mimics the sample_devotional fixture prompts
        section = BeStillSection(
            prompts=[
                "Sit quietly for two minutes before reading further.",
                "What word or phrase from today's scripture stays with you?",
                "Offer that word back to God in silence.",
            ]
        )
        assert _result(validate_be_still(section), "BE_STILL_SECOND_PERSON") == "pass"
        assert _result(validate_be_still(section), "BE_STILL_PROMPT_COUNT") == "pass"
