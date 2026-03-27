"""llm_grammar_advisor_core.py — LLM-backed prose review of devotional exposition.

The grammar advisor uses Claude or Codex to read devotional exposition and evaluate
it for sentence clarity, paragraph rhythm, and prose discipline.
This replaces regex-only checks with expert AI prose review.

Provider is configured via DEVG_LLM_PROVIDER (default: claude).
Worker override: DEVG_LLM_GRAMMAR_ADVISOR.
"""
from __future__ import annotations

import json
import re
from typing import Any

from src.llm.interfaces import LLMClient
from src.llm.router import get_llm_client


_REVIEW_PROMPT_TEMPLATE = """\
You are an expert prose coach for devotional publishing at a premium level.

Your task: Evaluate the following devotional exposition for prose clarity, \
sentence rhythm, and paragraph quality. Your job is prose discipline only — \
do not evaluate theology. Flag mechanical prose failures: repetitive sentence \
openings, overlong sentences, stacked abstractions, or template-sounding language.

PASSAGE: {focal_reference}

EXPOSITION TO REVIEW:
{exposition_text}

EVALUATION RUBRIC:
1. Are sentences clear and grammatically stable?
2. Is there unnecessary repetition in sentence openings or cadence?
3. Do sentences vary appropriately in length and structure?
4. Does the prose read as shaped writing rather than a template?
5. Are there overlong sentences (more than 30 words) that should be tightened?
6. Do paragraphs flow, or do they stack disconnected abstractions?

Respond ONLY with a valid JSON object. No preamble or explanation outside the JSON.

{{
  "score": <integer 0-100>,
  "status": "<pass|revise|fail>",
  "findings": [
    {{
      "title": "<short prose problem title>",
      "severity": "<high|medium|low>",
      "rationale": "<specific observation — quote the problematic phrase or pattern>",
      "recommendation": "<concrete revision direction>"
    }}
  ],
  "metrics": {{
    "overlong_sentence_count": <int>,
    "repetitive_opening_count": <int>
  }},
  "summary": "<one sentence describing the prose quality>"
}}

Scoring guide: 80-100 = pass (clear, varied, disciplined prose); \
60-79 = revise (fixable mechanical issues); \
0-59 = fail (template-sounding, repetitive, or grammatically unstable).
"""


def _parse_llm_response(raw: str) -> dict[str, Any]:
    """Extract and parse JSON from LLM response, with fallback."""
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    return {
        "score": 0,
        "status": "fail",
        "findings": [
            {
                "title": "Grammar review could not parse LLM response",
                "severity": "high",
                "rationale": f"LLM returned an unparseable response: {raw[:200]}",
                "recommendation": "Re-run grammar review and inspect LLM output format.",
            }
        ],
        "metrics": {"overlong_sentence_count": 0, "repetitive_opening_count": 0},
        "summary": "Grammar review blocked — LLM response was malformed.",
    }


def build_llm_grammar_review(
    exposition_text: str,
    *,
    focal_reference: str,
    llm: LLMClient | None = None,
) -> dict[str, Any]:
    """Evaluate devotional exposition prose quality via LLM.

    The LLM reads the exposition and provides expert prose review including
    pass/fail status, specific findings, and prose metrics.

    Args:
        exposition_text: The exposition paragraph(s) to review.
        focal_reference: The specific passage reference (e.g., "Colossians 3:1-4").
        llm: Optional LLMClient override (uses DEVG_LLM_GRAMMAR_ADVISOR by default).

    Returns:
        Dict with keys: score (int), status (str), findings (list),
        metrics (dict with overlong_sentence_count and repetitive_opening_count),
        summary (str).
    """
    if llm is None:
        llm = get_llm_client(worker="grammar_advisor")

    prompt = _REVIEW_PROMPT_TEMPLATE.format(
        focal_reference=focal_reference,
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

    # Ensure required fields
    if not isinstance(result.get("findings"), list):
        result["findings"] = []
    if not isinstance(result.get("metrics"), dict):
        result["metrics"] = {"overlong_sentence_count": 0, "repetitive_opening_count": 0}

    return result
