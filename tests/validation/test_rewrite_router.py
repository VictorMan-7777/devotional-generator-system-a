"""Tests for src/validation/rewrite_router.py — FR-78 rewrite routing signal."""
import pytest

from src.models.validation import RewriteSignal, ValidatorAssessment
from src.validation.rewrite_router import route


def _fail(check_id: str) -> ValidatorAssessment:
    return ValidatorAssessment(
        check_id=check_id,
        result="fail",
        reason_code=f"{check_id}_VIOLATION",
        explanation="Test failure.",
    )


def _pass_a(check_id: str) -> ValidatorAssessment:
    return ValidatorAssessment(
        check_id=check_id,
        result="pass",
        reason_code="",
        explanation="",
    )


class TestSignal:
    def test_attempt_1_returns_auto_rewrite(self):
        decision = route([_fail("EXPOSITION_WORD_COUNT")], attempt_number=1)
        assert decision.signal == RewriteSignal.AUTO_REWRITE

    def test_attempt_2_returns_human_review(self):
        decision = route([_fail("EXPOSITION_WORD_COUNT")], attempt_number=2)
        assert decision.signal == RewriteSignal.HUMAN_REVIEW

    def test_attempt_3_returns_human_review(self):
        decision = route([_fail("EXPOSITION_WORD_COUNT")], attempt_number=3)
        assert decision.signal == RewriteSignal.HUMAN_REVIEW

    def test_large_attempt_number_returns_human_review(self):
        decision = route([_fail("X")], attempt_number=99)
        assert decision.signal == RewriteSignal.HUMAN_REVIEW


class TestFailedAssessments:
    def test_only_failing_assessments_returned(self):
        assessments = [
            _pass_a("EXPOSITION_WORD_COUNT"),
            _fail("EXPOSITION_VOICE"),
            _pass_a("BE_STILL_PROMPT_COUNT"),
            _fail("PRAYER_WORD_COUNT"),
        ]
        decision = route(assessments, attempt_number=1)
        assert len(decision.failed_assessments) == 2
        ids = {a.check_id for a in decision.failed_assessments}
        assert ids == {"EXPOSITION_VOICE", "PRAYER_WORD_COUNT"}

    def test_all_failing_assessments_returned(self):
        assessments = [_fail("A"), _fail("B"), _fail("C")]
        decision = route(assessments, attempt_number=1)
        assert len(decision.failed_assessments) == 3

    def test_empty_input_returns_empty_failed(self):
        decision = route([], attempt_number=1)
        assert decision.failed_assessments == []

    def test_all_passing_returns_empty_failed(self):
        decision = route([_pass_a("X"), _pass_a("Y")], attempt_number=2)
        assert decision.failed_assessments == []

    def test_failed_assessments_preserve_reason_codes(self):
        decision = route([_fail("EXPOSITION_VOICE")], attempt_number=1)
        assert decision.failed_assessments[0].reason_code == "EXPOSITION_VOICE_VIOLATION"
