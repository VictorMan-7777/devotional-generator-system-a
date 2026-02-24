"""rewrite_router.py — FR-78 rewrite routing signal.

Returns a signal (AUTO_REWRITE or HUMAN_REVIEW) based on validator
results and attempt number. Does not perform any rewriting.
"""
from __future__ import annotations

from src.models.validation import RewriteDecision, RewriteSignal, ValidatorAssessment


def route(
    assessments: list[ValidatorAssessment],
    attempt_number: int,
) -> RewriteDecision:
    """Determine the rewrite routing signal for a set of validator assessments.

    Args:
        assessments: All assessments returned by a validator run.
        attempt_number: 1-based count of how many generation attempts have
                        been made for this section (1 = first attempt, etc.).

    Returns:
        RewriteDecision with signal AUTO_REWRITE (attempt 1) or HUMAN_REVIEW
        (attempt 2 or greater). failed_assessments contains only the failing
        assessments from the input list.

    Only called when at least one assessment has result == "fail".
    If all assessments pass, the caller should not invoke this function.
    """
    failed = [a for a in assessments if a.result == "fail"]
    signal = (
        RewriteSignal.AUTO_REWRITE
        if attempt_number == 1
        else RewriteSignal.HUMAN_REVIEW
    )
    return RewriteDecision(signal=signal, failed_assessments=failed)
