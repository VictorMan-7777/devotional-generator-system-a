"""llm_action_steps_core.py — LLM Action Steps trainer: evaluates deterministic output.

The action writer is a deterministic pipeline worker (_build_action_steps in
real_section_generator.py). This module provides the LLM TRAINER that reads
what the deterministic writer produced and evaluates it with expert eyes —
checking whether action steps are specific, same-day applicable, and flow from
the Be Still section rather than from the exposition directly.

Provider is configured via DEVG_LLM_PROVIDER (default: claude).
Trainer uses the cross provider (LLM evaluating must differ from generator AI).

Pass threshold: score >= 80 (out of 100).

PRD evaluation criteria (FR-29 through FR-34):
  FR-29: Steps explicitly reference or arise from the Be Still section — not
         the exposition directly. Connector phrase required.
  FR-30: 1–3 items, specific, same-day applicable.
  FR-31: Obedience framed as response to revelation, not achievement.
  FR-32: Does not resolve the tension named in Be Still.
  FR-33: Active expectation and partnership with God — no passive compliance.
  FR-34: At least one step acknowledges faithful response may feel unfamiliar,
         grounded in God's faithfulness (not reader's capacity).
"""
from __future__ import annotations

import json
import re
from typing import Any

from src.llm.router import get_cross_llm_client
from src.llm.interfaces import LLMClient


# ── Deterministic pre-check ───────────────────────────────────────────────────

_GENERIC_PHRASES = (
    "pray about it",
    "spend time in prayer",
    "read your bible",
    "trust god",
    "be a good person",
    "show kindness",
    "do your best",
    "stay positive",
    "keep the faith",
    "be thankful",
    "make time for god",
)

_PASSIVE_PHRASES = (
    "wait for god",
    "let go and let god",
    "just trust",
    "whatever happens",
    "god will handle it",
    "don't worry about",
)

_CONNECTOR_PRESENT = re.compile(
    r"(?i)(in light of|based on what|having listened|from what god|"
    r"because .{3,40} calls|after sitting|from your time|"
    r"having sat with|what you heard)",
)


def evaluate_action_steps_section(
    items: list[str],
    connector_phrase: str,
    *,
    passage_reference: str,
    be_still_prompts: list[str],
) -> dict[str, Any]:
    """Deterministic structural scoring for an Action Steps section.

    Returns dict with: status, score, findings, metrics.
    """
    findings: list[str] = []
    score = 100

    count = len(items)
    if not (1 <= count <= 3):
        findings.append(f"Item count is {count}; must be 1–3.")
        score -= 25

    if not connector_phrase or not connector_phrase.strip():
        findings.append("Connector phrase is missing.")
        score -= 20
    elif not _CONNECTOR_PRESENT.search(connector_phrase):
        findings.append(
            f"Connector phrase does not reference Be Still explicitly: {connector_phrase!r}"
        )
        score -= 10

    all_text = " ".join(items).lower()
    generic_count = sum(1 for phrase in _GENERIC_PHRASES if phrase in all_text)
    if generic_count >= 2:
        findings.append(f"{generic_count} generic action phrases detected — steps may not be passage-specific.")
        score -= generic_count * 8
    elif generic_count == 1:
        findings.append("1 generic action phrase detected.")
        score -= 6

    passive_count = sum(1 for phrase in _PASSIVE_PHRASES if phrase in all_text)
    if passive_count:
        findings.append(f"{passive_count} passive/fatalistic phrase(s) detected — violates active expectation rule.")
        score -= passive_count * 10

    short_items = [item for item in items if len(item.split()) < 6]
    if short_items:
        findings.append(
            f"{len(short_items)} item(s) are fewer than 6 words — likely too vague to be same-day applicable."
        )
        score -= len(short_items) * 8

    score = max(0, score)
    status = "pass" if score >= 80 else "revise" if score >= 60 else "fail"

    return {
        "status": status,
        "score": score,
        "findings": findings,
        "metrics": {
            "item_count": count,
            "connector_present": bool(connector_phrase and connector_phrase.strip()),
            "connector_references_be_still": bool(_CONNECTOR_PRESENT.search(connector_phrase or "")),
            "generic_phrase_count": generic_count,
            "passive_phrase_count": passive_count,
            "short_item_count": len(short_items),
        },
    }


# ── LLM Action Steps Trainer ──────────────────────────────────────────────────

_ACTION_STEPS_TRAINER_PROMPT = """\
You are an expert action steps trainer evaluating steps produced by a \
deterministic devotional writer.

Your task: Read the action steps below and evaluate whether they are specific, \
same-day applicable, and genuinely flow from the Be Still section — not from \
the exposition directly. Steps that could appear in any devotional, or that \
sound like generic spiritual-productivity advice, are failures.

PASSAGE: {passage_reference}
PASSAGE TEXT (first 400 chars):
{passage_text}

BE STILL PROMPTS (the reader has just sat with these — steps must flow from here):
{be_still_formatted}

CONNECTOR PHRASE: {connector_phrase}

ACTION STEPS ({item_count} items):
{items_formatted}

DETERMINISTIC SCORING FINDINGS:
{findings_text}

EVALUATION RUBRIC (PRD FR-29 through FR-34):
1. Do the steps genuinely flow from the Be Still prompts above, not from the exposition directly?
2. Is each step specific enough to be attempted TODAY — not a vague ongoing disposition?
3. Is obedience framed as response to what God has revealed, not as effort to earn favor?
4. Do the steps convey active expectation and partnership with God — not passive compliance or resignation?
5. Does at least one step acknowledge that faithful response may feel unfamiliar or uncertain,
   grounding that acknowledgment in God's faithfulness (not the reader's capacity)?
6. Do the steps leave the outcome in God's hands rather than resolving the tension from Be Still?

Respond ONLY with valid JSON. No preamble or explanation outside the JSON.

{{
  "score": <integer 0–100>,
  "status": "<pass|revise|fail>",
  "flows_from_be_still": <true|false>,
  "same_day_applicable": <true|false>,
  "findings": [
    "<specific observation referencing actual step content>"
  ],
  "priority_fix": "<the single most important improvement the action writer should make>",
  "proposed_code_changes": [
    {{
      "file_path": "<relative path, e.g. src/generation/real_section_generator.py>",
      "objective": "<one-line description>",
      "change_description": "<concrete description: what to change, where, and to what>",
      "rationale": "<why this is a structural code problem, not a training problem>"
    }}
  ]
}}

Score guide: pass >= 80, revise >= 60, fail < 60. Status must match the score.

proposed_code_changes: Only populate if you observe a structural pattern that \
CANNOT be fixed by training — e.g. a connector phrase that always references \
the exposition instead of Be Still, a hardcoded generic step that appears in \
every output, or items that are systematically too vague to be same-day \
applicable. Leave empty if the issue is training quality.
"""


def _parse_action_steps_trainer_response(raw: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {
        "score": 0,
        "status": "revise",
        "flows_from_be_still": False,
        "same_day_applicable": False,
        "findings": [f"Trainer could not parse LLM response: {raw[:200]}"],
        "priority_fix": "Re-run trainer evaluation and inspect LLM output format.",
    }


def build_llm_action_steps_trainer_review(
    items: list[str],
    connector_phrase: str,
    *,
    passage_reference: str,
    passage_text: str,
    be_still_prompts: list[str],
    llm: LLMClient | None = None,
) -> dict[str, Any]:
    """LLM trainer evaluates deterministic Action Steps and provides expert coaching.

    Args:
        items:             The action step items produced by the deterministic writer.
        connector_phrase:  The connector phrase produced by the deterministic writer.
        passage_reference: Scripture passage reference.
        passage_text:      The scripture text for this day.
        be_still_prompts:  The Be Still prompts for this day — steps must flow from these.
        llm:               Optional LLMClient override (uses cross provider by default).

    Returns:
        Dict with: score (int), status (str), flows_from_be_still (bool),
        same_day_applicable (bool), findings (list), priority_fix (str),
        proposed_code_changes (list).
    """
    if llm is None:
        llm = get_cross_llm_client(worker="action_writer")

    deterministic = evaluate_action_steps_section(
        items,
        connector_phrase,
        passage_reference=passage_reference,
        be_still_prompts=be_still_prompts,
    )
    findings = list(deterministic.get("findings") or [])
    findings_text = "\n".join(f"- {f}" for f in findings) if findings else "No heuristic findings."

    be_still_formatted = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(be_still_prompts))
    items_formatted = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))

    prompt = _ACTION_STEPS_TRAINER_PROMPT.format(
        passage_reference=passage_reference,
        passage_text=passage_text[:400],
        be_still_formatted=be_still_formatted,
        connector_phrase=connector_phrase,
        item_count=len(items),
        items_formatted=items_formatted,
        findings_text=findings_text,
    )

    raw = llm.generate(prompt)
    result = _parse_action_steps_trainer_response(raw)

    score = max(0, min(100, int(result.get("score") or 0)))
    status = "pass" if score >= 80 else "revise" if score >= 60 else "fail"

    return {
        "score": score,
        "status": status,
        "flows_from_be_still": bool(result.get("flows_from_be_still")),
        "same_day_applicable": bool(result.get("same_day_applicable")),
        "findings": result.get("findings") or [],
        "priority_fix": result.get("priority_fix") or "",
        "deterministic_findings": findings,
        "proposed_code_changes": result.get("proposed_code_changes") or [],
    }
