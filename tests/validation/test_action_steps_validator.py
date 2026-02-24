"""Tests for src/validation/action_steps.py — FR-76 Action Steps validator."""
import pytest

from src.models.devotional import ActionStepsSection
from src.validation.action_steps import validate_action_steps


def _result(results, check_id: str) -> str:
    for a in results:
        if a.check_id == check_id:
            return a.result
    raise KeyError(check_id)


_CONNECTOR = "As you move through this day:"
_ITEM = "Choose one person today and offer a word of encouragement."


class TestItemCount:
    def test_one_item_passes(self):
        section = ActionStepsSection(items=[_ITEM], connector_phrase=_CONNECTOR)
        assert _result(validate_action_steps(section), "ACTION_STEPS_COUNT") == "pass"

    def test_three_items_passes(self):
        section = ActionStepsSection(items=[_ITEM] * 3, connector_phrase=_CONNECTOR)
        assert _result(validate_action_steps(section), "ACTION_STEPS_COUNT") == "pass"

    def test_two_items_passes(self):
        section = ActionStepsSection(items=[_ITEM] * 2, connector_phrase=_CONNECTOR)
        assert _result(validate_action_steps(section), "ACTION_STEPS_COUNT") == "pass"

    def test_zero_items_fails(self):
        section = ActionStepsSection(items=[], connector_phrase=_CONNECTOR)
        result = _result(validate_action_steps(section), "ACTION_STEPS_COUNT")
        assert result == "fail"
        assessment = next(
            a for a in validate_action_steps(section) if a.check_id == "ACTION_STEPS_COUNT"
        )
        assert assessment.reason_code == "ACTION_STEPS_COUNT_VIOLATION"

    def test_four_items_fails(self):
        section = ActionStepsSection(items=[_ITEM] * 4, connector_phrase=_CONNECTOR)
        assert _result(validate_action_steps(section), "ACTION_STEPS_COUNT") == "fail"


class TestConnectorPhrase:
    def test_present_connector_passes(self):
        section = ActionStepsSection(items=[_ITEM], connector_phrase=_CONNECTOR)
        assert _result(validate_action_steps(section), "ACTION_STEPS_CONNECTOR_PHRASE") == "pass"

    def test_empty_connector_fails(self):
        section = ActionStepsSection(items=[_ITEM], connector_phrase="")
        result = _result(validate_action_steps(section), "ACTION_STEPS_CONNECTOR_PHRASE")
        assert result == "fail"
        assessment = next(
            a
            for a in validate_action_steps(section)
            if a.check_id == "ACTION_STEPS_CONNECTOR_PHRASE"
        )
        assert assessment.reason_code == "ACTION_STEPS_CONNECTOR_PHRASE_MISSING"

    def test_whitespace_only_connector_fails(self):
        section = ActionStepsSection(items=[_ITEM], connector_phrase="   ")
        assert _result(validate_action_steps(section), "ACTION_STEPS_CONNECTOR_PHRASE") == "fail"

    def test_single_word_connector_passes(self):
        section = ActionStepsSection(items=[_ITEM], connector_phrase="Today:")
        assert _result(validate_action_steps(section), "ACTION_STEPS_CONNECTOR_PHRASE") == "pass"
