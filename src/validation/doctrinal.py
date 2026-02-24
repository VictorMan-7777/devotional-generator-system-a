"""doctrinal.py — Section 10.1/10.2 doctrinal guardrail engine.

Pattern-based checks only. No LLM inference. Returns an empty list
when the text is clean; returns one ValidatorAssessment per matched
pattern category when violations are detected.
"""
from __future__ import annotations

import re

from src.models.validation import ValidatorAssessment

# Prosperity gospel patterns.
_PROSPERITY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bGod wants you\s+(rich|wealthy|successful|prosperous)\b", re.IGNORECASE),
    re.compile(r"\bfinancial blessing\b", re.IGNORECASE),
    re.compile(r"\bname it and claim it\b", re.IGNORECASE),
    re.compile(r"\bhealth and wealth\b", re.IGNORECASE),
    re.compile(r"\bwealth gospel\b", re.IGNORECASE),
    re.compile(r"\bprosperity gospel\b", re.IGNORECASE),
]

# Works-based merit patterns.
_WORKS_MERIT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\bearn(ed|s)?\s+(your|God'?s)\s+(love|forgiveness|salvation|favor|grace)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdeserve(d|s)?\s+(grace|mercy|blessing|salvation|forgiveness)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bgood enough for God\b", re.IGNORECASE),
    re.compile(r"\bworks?\s+your way\s+to (heaven|salvation|God)\b", re.IGNORECASE),
]


def _first_match(patterns: list[re.Pattern[str]], text: str) -> re.Match[str] | None:
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            return m
    return None


def check_doctrinal(text: str) -> list[ValidatorAssessment]:
    """Run pattern-based doctrinal guardrail checks on arbitrary text.

    Returns an empty list if no patterns match.
    Returns one ValidatorAssessment per matched category (not per occurrence).
    """
    results: list[ValidatorAssessment] = []

    prosperity_match = _first_match(_PROSPERITY_PATTERNS, text)
    if prosperity_match:
        results.append(
            ValidatorAssessment(
                check_id="DOCTRINAL_PROSPERITY",
                result="fail",
                reason_code="DOCTRINAL_PROSPERITY_GOSPEL",
                explanation=(
                    "Text contains prosperity gospel language, which is prohibited "
                    "per Section 10.1 doctrinal guardrails."
                ),
                evidence=prosperity_match.group(0),
            )
        )

    works_match = _first_match(_WORKS_MERIT_PATTERNS, text)
    if works_match:
        results.append(
            ValidatorAssessment(
                check_id="DOCTRINAL_WORKS_MERIT",
                result="fail",
                reason_code="DOCTRINAL_WORKS_MERIT",
                explanation=(
                    "Text contains works-based merit language, which is prohibited "
                    "per Section 10.2 doctrinal guardrails."
                ),
                evidence=works_match.group(0),
            )
        )

    return results
