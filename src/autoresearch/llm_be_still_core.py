"""llm_be_still_core.py — LLM Be Still trainer: evaluates deterministic Be Still output.

The Be Still writer is a deterministic pipeline worker (_build_be_still in
real_section_generator.py). This module provides the LLM TRAINER that reads
what the deterministic writer produced and evaluates it with expert eyes —
checking whether prompts genuinely arise from the passage and guide the reader
from inward receptivity to outward felt need, or whether they are generic
spiritual-stillness filler.

Provider is configured via DEVG_LLM_PROVIDER (default: claude).
Trainer uses the cross provider (LLM evaluating must differ from generator AI).

Pass threshold: score >= 80 (out of 100).

PRD evaluation criteria (FR-22 through FR-26):
  FR-22: Prompts arise from exposition — no new concepts introduced.
  FR-23: First prompt directs to stillness and receptivity.
  FR-24: Inward-to-outward sequence; final prompt creates felt need for action.
  FR-25: Second-person ("you") throughout.
  FR-26: Questions or directives only — never answered within the section.
"""
from __future__ import annotations

import json
import re
from typing import Any

from src.llm.router import get_cross_llm_client
from src.llm.interfaces import LLMClient


# ── Deterministic pre-check ───────────────────────────────────────────────────

_STILLNESS_OPENERS = (
    "sit", "still", "quiet", "silence", "pause", "rest", "settle",
    "read", "close", "breathe", "slow",
)

_GENERIC_PHRASES = (
    "god is with you",
    "trust in him",
    "he loves you",
    "in his presence",
    "spend time with god",
    "open your heart",
    "listen to his voice",
    "draw near",
    "daily walk",
    "spiritual journey",
    "remind yourself",
    "just be still",
)

_SECOND_PERSON = re.compile(r"\b(you|your)\b", re.IGNORECASE)


def _first_prompt_is_stillness(prompt: str) -> bool:
    lowered = prompt.strip().lower()
    return any(lowered.startswith(word) or f" {word} " in lowered for word in _STILLNESS_OPENERS)


def _is_question_or_directive(prompt: str) -> bool:
    stripped = prompt.strip()
    return stripped.endswith("?") or stripped[0].isupper()


def evaluate_be_still_section(
    prompts: list[str],
    *,
    passage_reference: str,
    passage_text: str,
) -> dict[str, Any]:
    """Deterministic structural scoring for a Be Still section.

    Returns dict with: status, score, findings, metrics.
    """
    findings: list[str] = []
    score = 100

    count = len(prompts)
    if not (3 <= count <= 5):
        findings.append(f"Prompt count is {count}; must be 3–5.")
        score -= 25

    if prompts:
        if not _first_prompt_is_stillness(prompts[0]):
            findings.append(
                f"First prompt does not open with a stillness/receptivity word: {prompts[0][:80]!r}"
            )
            score -= 15

    has_second_person = any(_SECOND_PERSON.search(p) for p in prompts)
    if not has_second_person:
        findings.append("No prompt contains second-person language (you/your).")
        score -= 15

    lowered_all = " ".join(prompts).lower()
    generic_count = sum(1 for phrase in _GENERIC_PHRASES if phrase in lowered_all)
    if generic_count >= 2:
        findings.append(f"{generic_count} generic stillness phrases detected — prompts may apply to any passage.")
        score -= generic_count * 8
    elif generic_count == 1:
        findings.append("1 generic stillness phrase detected.")
        score -= 5

    ref_tokens = set(re.findall(r"[A-Za-z0-9]+", passage_reference.lower()))
    prompts_lower = [p.lower() for p in prompts]
    ref_mentioned = any(
        any(token in p for token in ref_tokens if len(token) > 2)
        for p in prompts_lower
    )
    if not ref_mentioned:
        findings.append(f"No prompt references the passage ({passage_reference}) explicitly.")
        score -= 10

    score = max(0, score)
    status = "pass" if score >= 80 else "revise" if score >= 60 else "fail"

    return {
        "status": status,
        "score": score,
        "findings": findings,
        "metrics": {
            "prompt_count": count,
            "has_second_person": has_second_person,
            "first_prompt_is_stillness": _first_prompt_is_stillness(prompts[0]) if prompts else False,
            "generic_phrase_count": generic_count,
            "passage_ref_mentioned": ref_mentioned,
        },
    }


# ── LLM Be Still Trainer ──────────────────────────────────────────────────────

_BE_STILL_TRAINER_PROMPT = """\
You are an expert Be Still section trainer evaluating prompts produced by a \
deterministic devotional writer.

Your task: Read the Be Still prompts below and evaluate whether they genuinely \
guide the reader from inward receptivity into a felt need for action — anchored \
to THIS passage — or whether they are generic stillness filler that could appear \
in any devotional.

PASSAGE: {passage_reference}
PASSAGE TEXT (first 400 chars):
{passage_text}

EXPOSITION (first 400 chars — the prompts must arise from this):
{exposition_text}

BE STILL PROMPTS ({prompt_count} prompts):
{prompts_formatted}

DETERMINISTIC SCORING FINDINGS:
{findings_text}

EVALUATION RUBRIC (PRD FR-22 through FR-26):
1. Does the first prompt genuinely invite stillness and receptivity, or does it rush to reflection?
2. Do the prompts move inward first (what does this reveal about God? about me?) then outward?
3. Does the final prompt create a felt need that would naturally flow into action — without resolving it?
4. Are the prompts genuinely passage-specific, or could they appear in any devotional?
5. Do prompts arise from the exposition above, or do they introduce new concepts not present there?
6. Are prompts written in second-person ("you") throughout?
7. Are prompts questions or directives — never answered within the section?

Respond ONLY with valid JSON. No preamble or explanation outside the JSON.

{{
  "score": <integer 0–100>,
  "status": "<pass|revise|fail>",
  "passage_anchored": <true|false>,
  "inward_to_outward": <true|false>,
  "findings": [
    "<specific observation referencing actual prompt content>"
  ],
  "priority_fix": "<the single most important improvement the Be Still writer should make>",
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
CANNOT be fixed by training — e.g. a hardcoded closing prompt that appears in \
every output regardless of passage, a missing inward-to-outward sequence in the \
template logic, or a prompt that answers itself. Leave empty if the issue is \
training quality, not structural code.
"""


def _parse_be_still_trainer_response(raw: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {
        "score": 0,
        "status": "revise",
        "passage_anchored": False,
        "inward_to_outward": False,
        "findings": [f"Trainer could not parse LLM response: {raw[:200]}"],
        "priority_fix": "Re-run trainer evaluation and inspect LLM output format.",
    }


def build_llm_be_still_trainer_review(
    prompts: list[str],
    *,
    passage_reference: str,
    passage_text: str,
    exposition_text: str,
    llm: LLMClient | None = None,
) -> dict[str, Any]:
    """LLM trainer evaluates a deterministic Be Still section and provides expert coaching.

    Args:
        prompts:           The Be Still prompts produced by the deterministic writer.
        passage_reference: Scripture passage reference (e.g. "Habakkuk 1:1-4").
        passage_text:      The scripture text for this day.
        exposition_text:   The exposition text — prompts must arise from this.
        llm:               Optional LLMClient override (uses cross provider by default).

    Returns:
        Dict with: score (int), status (str), passage_anchored (bool),
        inward_to_outward (bool), findings (list), priority_fix (str),
        proposed_code_changes (list).
    """
    if llm is None:
        llm = get_cross_llm_client(worker="be_still_writer")

    deterministic = evaluate_be_still_section(
        prompts,
        passage_reference=passage_reference,
        passage_text=passage_text,
    )
    findings = list(deterministic.get("findings") or [])
    findings_text = "\n".join(f"- {f}" for f in findings) if findings else "No heuristic findings."

    prompts_formatted = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(prompts))

    prompt = _BE_STILL_TRAINER_PROMPT.format(
        passage_reference=passage_reference,
        passage_text=passage_text[:400],
        exposition_text=exposition_text[:400],
        prompt_count=len(prompts),
        prompts_formatted=prompts_formatted,
        findings_text=findings_text,
    )

    raw = llm.generate(prompt)
    result = _parse_be_still_trainer_response(raw)

    score = max(0, min(100, int(result.get("score") or 0)))
    status = "pass" if score >= 80 else "revise" if score >= 60 else "fail"

    return {
        "score": score,
        "status": status,
        "passage_anchored": bool(result.get("passage_anchored")),
        "inward_to_outward": bool(result.get("inward_to_outward")),
        "findings": result.get("findings") or [],
        "priority_fix": result.get("priority_fix") or "",
        "deterministic_findings": findings,
        "proposed_code_changes": result.get("proposed_code_changes") or [],
    }
