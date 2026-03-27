"""llm_theological_reviewer_core.py — LLM-backed theological review of exposition text.

The theological reviewer uses Claude or Codex to read devotional exposition and evaluate
it for passage faithfulness, theological accuracy, and doctrinal boundary compliance.
This replaces heuristic-only review with expert AI judgment.

Provider is configured via DEVG_LLM_PROVIDER (default: claude).
Worker override: DEVG_LLM_THEOLOGICAL_REVIEWER.
"""
from __future__ import annotations

import json
import re
from typing import Any

from src.llm.interfaces import LLMClient
from src.llm.router import get_llm_client


_REVIEW_PROMPT_TEMPLATE = """\
You are an expert theological reviewer for devotional publishing at a seminary level.

Your task: Evaluate the following devotional exposition for theological faithfulness \
to its assigned passage. Flag any flattening, sentimental drift, doctrinal overreach, \
or generic language that could have been written without reading the text.

PASSAGE: {focal_reference}
TOPIC: {topic}

SCRIPTURE TEXT:
{passage_text}

EXPOSITION TO REVIEW:
{exposition_text}

EVALUATION RUBRIC:
1. Does the exposition draw from specific verse details rather than paraphrasing the whole chapter?
2. Could this exposition have been written without reading the assigned passage? \
   (Generic drift — if yes, this is a failure.)
3. Does it respect the passage's theological weight without softening or inflating it?
4. Is there doctrinal drift, flattening, or sentimental substitution for the text's actual burden?
5. Are all theological claims accurate and consistent with the specific passage?

Respond ONLY with a valid JSON object. No preamble or explanation outside the JSON.

{{
  "score": <integer 0-100>,
  "status": "<pass|revise|fail>",
  "passage_grounded": <true|false>,
  "theological_drift_detected": <true|false>,
  "findings": [
    {{
      "title": "<short title>",
      "severity": "<high|medium|low>",
      "rationale": "<specific observation referencing the text>",
      "recommendation": "<concrete correction>"
    }}
  ],
  "summary": "<one sentence describing the theological quality of this exposition>"
}}

Scoring guide: 80-100 = pass (theologically sound, passage-faithful); \
60-79 = revise (fixable issues, not fully passage-anchored); \
0-59 = fail (generic, drifted, or doctrinally unsound).
"""


def _parse_llm_response(raw: str) -> dict[str, Any]:
    """Extract and parse JSON from LLM response, with fallback."""
    # Try to find JSON block if the LLM included surrounding text
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    # Fallback: return a minimal failure record
    return {
        "score": 0,
        "status": "fail",
        "passage_grounded": False,
        "theological_drift_detected": True,
        "findings": [
            {
                "title": "Theological review could not parse LLM response",
                "severity": "high",
                "rationale": f"LLM returned an unparseable response: {raw[:200]}",
                "recommendation": "Re-run the theological review and inspect the LLM output format.",
            }
        ],
        "summary": "Theological review blocked — LLM response was malformed.",
    }


def build_llm_theological_review(
    exposition_text: str,
    *,
    passage_text: str,
    focal_reference: str,
    topic: str = "",
    llm: LLMClient | None = None,
) -> dict[str, Any]:
    """Evaluate devotional exposition text for theological quality via LLM.

    The LLM reads the exposition and passage, then provides expert theological
    evaluation including pass/fail status, specific findings, and a score.

    Args:
        exposition_text: The exposition paragraph(s) to review.
        passage_text: The scripture text for context.
        focal_reference: The specific passage reference (e.g., "Habakkuk 1:2-4").
        topic: Optional topic label to anchor the evaluation.
        llm: Optional LLMClient override (uses DEVG_LLM_THEOLOGICAL_REVIEWER by default).

    Returns:
        Dict with keys: score (int), status (str), passage_grounded (bool),
        theological_drift_detected (bool), findings (list), summary (str).
    """
    if llm is None:
        llm = get_llm_client(worker="theological_reviewer")

    prompt = _REVIEW_PROMPT_TEMPLATE.format(
        focal_reference=focal_reference,
        topic=topic or focal_reference,
        passage_text=(passage_text or "").strip()[:1200],
        exposition_text=(exposition_text or "").strip()[:1500],
    )

    raw = llm.generate(prompt)
    result = _parse_llm_response(raw)

    # Normalize score and status
    score = int(result.get("score") or 0)
    if score >= 80:
        status = "pass"
    elif score >= 60:
        status = "revise"
    else:
        status = "fail"
    result["score"] = score
    result["status"] = status

    # Ensure findings is a list
    if not isinstance(result.get("findings"), list):
        result["findings"] = []

    return result


def evaluate_theological_review_quality(result: dict[str, Any]) -> dict[str, Any]:
    """Score a theological review result for training purposes.

    Checks whether the review produced specific, passage-anchored findings
    rather than generic observations. Used to evaluate the reviewer's own quality.

    Returns:
        Dict with: score (int), status (str), specificity_rate (float).
    """
    findings = result.get("findings") or []
    total = len(findings)
    if total == 0:
        return {"score": result.get("score", 0), "status": result.get("status", "fail"), "specificity_rate": 1.0}

    # Count findings that reference the text (have specific rationale)
    specific = sum(
        1 for f in findings
        if len(str(f.get("rationale") or "").split()) >= 10
    )
    specificity_rate = specific / total if total else 0.0

    return {
        "score": result.get("score", 0),
        "status": result.get("status", "fail"),
        "specificity_rate": specificity_rate,
        "finding_count": total,
        "specific_finding_count": specific,
    }
