"""llm_prayer_writer_core.py — LLM Prayer Writer trainer: evaluates deterministic Prayer output.

The Prayer writer is a deterministic pipeline worker (_build_prayer in
real_section_generator.py). This module provides the LLM TRAINER that reads
what the deterministic writer produced and evaluates it with expert eyes —
checking whether the prayer genuinely arises from the day's passage and
pastoral burden, or whether it is generic devotional filler that could appear
in any closing prayer.

Provider is configured via DEVG_LLM_PROVIDER (default: claude).
Trainer uses the cross provider (LLM evaluating must differ from generator AI).

Pass threshold: score >= 80 (out of 100).

PRD evaluation criteria for prayer:
  PR-01: Prayer stays inside the passage horizon — no concepts outside the day's text.
  PR-02: Addresses God directly (Father/Lord/Holy Spirit appropriate to text).
  PR-03: Reflects the pastoral burden and theological lane of the day's outline.
  PR-04: Contains specific vocabulary from the passage — not generic devotional filler.
  PR-05: Tone matches the passage (lament passages get lament prayers, not comfort prayers).
  PR-06: Ends with "Amen." — structural check performed deterministically.
  PR-07: Contains at least one petition grounded in the day's focus clause.
  PR-08: Does NOT answer questions within the prayer — prayers petition, not explain.
"""
from __future__ import annotations

import json
import re
from typing import Any

from src.llm.router import get_cross_llm_client
from src.llm.interfaces import LLMClient


# ── Deterministic pre-check ───────────────────────────────────────────────────

_GENERIC_PRAYER_PHRASES = (
    "be with us",
    "guide us",
    "bless us",
    "thank you for this day",
    "thank you for your blessings",
    "help us to be",
    "help us to live",
    "in jesus name",
    "in jesus' name",
    "we ask these things",
    "we pray these things",
    "your will be done",
    "draw us closer",
    "let your light shine",
    "may we always",
    "teach us to love",
    "open our eyes",
    "give us strength",
    "protect us",
    "watch over us",
)

_DIRECT_ADDRESS = re.compile(
    r"\b(Father|Lord|Holy Spirit|God|Heavenly Father|Lord God|Christ|Jesus)\b",
    re.IGNORECASE,
)

_PETITION_VERBS = re.compile(
    r"\b(keep|teach|guard|strengthen|help|grant|give|make|turn|lift|hold|lead|fill|press|bring|let|do not let|do not|may we|forgive|deliver|restore)\b",
    re.IGNORECASE,
)


def evaluate_prayer_section(
    prayer_text: str,
    *,
    passage_reference: str,
    passage_text: str,
    editorial_brief: str = "",
) -> dict[str, Any]:
    """Deterministic structural scoring for a Prayer section.

    Returns dict with: status, score, findings, metrics.
    """
    findings: list[str] = []
    score = 100

    # PR-06: Must end with "Amen."
    stripped = prayer_text.strip()
    ends_with_amen = stripped.endswith("Amen.")
    if not ends_with_amen:
        findings.append("Prayer does not end with 'Amen.'")
        score -= 20

    # PR-02: Must address God directly
    has_direct_address = bool(_DIRECT_ADDRESS.search(prayer_text))
    if not has_direct_address:
        findings.append("Prayer does not address God directly (Father/Lord/Holy Spirit).")
        score -= 20

    # PR-07: Must contain at least one petition verb
    has_petition = bool(_PETITION_VERBS.search(prayer_text))
    if not has_petition:
        findings.append("Prayer contains no petition verbs — prayers must petition, not merely declare.")
        score -= 15

    # PR-08: Does not answer its own questions
    questions = re.findall(r"[^.!?]*\?", prayer_text)
    if questions:
        findings.append(
            f"Prayer contains {len(questions)} question(s) — prayers should not pose questions they might answer."
        )
        score -= len(questions) * 8

    # PR-04: Generic phrase check
    lowered = prayer_text.lower()
    generic_count = sum(1 for phrase in _GENERIC_PRAYER_PHRASES if phrase in lowered)
    if generic_count >= 3:
        findings.append(
            f"{generic_count} generic devotional phrases detected — prayer may apply to any passage, not this one."
        )
        score -= generic_count * 6
    elif generic_count >= 1:
        findings.append(f"{generic_count} generic devotional phrase(s) detected.")
        score -= generic_count * 3

    # PR-01: Passage reference should appear or passage vocabulary should be present
    ref_tokens = set(re.findall(r"[A-Za-z0-9]+", passage_reference.lower()))
    prayer_lower = prayer_text.lower()
    ref_mentioned = any(
        token in prayer_lower for token in ref_tokens if len(token) > 2
    )
    if not ref_mentioned:
        findings.append(
            f"Prayer does not reference the passage ({passage_reference}) or its key vocabulary."
        )
        score -= 10

    # Length check: 8–12 sentences expected
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", stripped) if s.strip()]
    sentence_count = len(sentences)
    if sentence_count < 6:
        findings.append(f"Prayer has only {sentence_count} sentence(s); expected 8–12.")
        score -= 15
    elif sentence_count > 16:
        findings.append(f"Prayer has {sentence_count} sentences; expected 8–12 (may be padded).")
        score -= 5

    score = max(0, score)
    status = "pass" if score >= 80 else "revise" if score >= 60 else "fail"

    return {
        "status": status,
        "score": score,
        "findings": findings,
        "metrics": {
            "ends_with_amen": ends_with_amen,
            "has_direct_address": has_direct_address,
            "has_petition": has_petition,
            "question_count": len(questions),
            "generic_phrase_count": generic_count,
            "passage_ref_mentioned": ref_mentioned,
            "sentence_count": sentence_count,
        },
    }


# ── LLM Prayer Writer Trainer ─────────────────────────────────────────────────

_PRAYER_TRAINER_PROMPT = """\
You are a lifelong seminary professor and pastoral theologian with decades of experience \
training ministers to write prayers that are genuinely anchored to the scriptural text before \
them. You hold a doctorate in systematic theology and pastoral ministry, have taught homiletics \
and liturgical theology at the graduate level, and have trained hundreds of pastors to write \
closing prayers that arise from the day's specific passage rather than recycling generic \
devotional language. You know the difference between a prayer that petitions from within a \
specific passage horizon and a prayer that merely gestures at scripture while filling space \
with universal platitudes.

Your task: Read the closing prayer below and evaluate whether it genuinely arises from the \
day's passage and pastoral burden — anchored to THIS text — or whether it is generic \
devotional filler that could appear after any reading anywhere.

PASSAGE: {passage_reference}
PASSAGE TEXT (first 400 chars):
{passage_text}

EDITORIAL BRIEF (pastoral burden and theological lane):
{editorial_brief}

CLOSING PRAYER:
{prayer_text}

DETERMINISTIC SCORING FINDINGS:
{findings_text}

EVALUATION RUBRIC (PR-01 through PR-08):
1. Does the prayer stay strictly inside the passage horizon — no concepts imported from outside today's text?
2. Does it address God directly in a mode appropriate to the passage (Father for provision texts, Lord for authority texts, Holy Spirit for transformation texts)?
3. Does it reflect the specific pastoral burden and theological lane of this day's outline — not a generic burden that could apply to any Sunday?
4. Does it contain specific vocabulary, images, or tensions drawn from the actual passage text?
5. Is the tone matched to the passage — lament passages require lament prayers, not consolation prayers?
6. Does it end with "Amen."?
7. Does it contain at least one petition grounded in the day's specific focus clause?
8. Does it avoid answering its own questions — prayers petition before God, they do not explain to the reader?

Respond ONLY with valid JSON. No preamble or explanation outside the JSON.

{{
  "score": <integer 0–100>,
  "status": "<pass|revise|fail>",
  "passage_anchored": <true|false>,
  "tone_matched": <true|false>,
  "findings": [
    "<specific observation referencing actual prayer content>"
  ],
  "priority_fix": "<the single most important improvement the Prayer writer should make>",
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
CANNOT be fixed by training — e.g. a hardcoded sentence that appears verbatim in \
every output regardless of passage, a petition that never changes across themes, \
or a closing formula that answers rather than petitions. Leave empty if the issue \
is training quality, not structural code.
"""


def _parse_prayer_trainer_response(raw: str) -> dict[str, Any]:
    # Strip markdown code fences that some models wrap around JSON responses.
    stripped = re.sub(r"```(?:json)?\s*", "", raw).strip()
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {
        "score": 0,
        "status": "revise",
        "passage_anchored": False,
        "tone_matched": False,
        "findings": [f"Trainer could not parse LLM response: {raw[:200]}"],
        "priority_fix": "Re-run trainer evaluation and inspect LLM output format.",
    }


def build_llm_prayer_trainer_review(
    prayer_text: str,
    *,
    passage_reference: str,
    passage_text: str,
    editorial_brief: str = "",
    llm: LLMClient | None = None,
) -> dict[str, Any]:
    """LLM trainer evaluates a deterministic Prayer section and provides expert coaching.

    Args:
        prayer_text:       The closing prayer produced by the deterministic writer.
        passage_reference: Scripture passage reference (e.g. "Habakkuk 1:1-4").
        passage_text:      The scripture text for this day.
        editorial_brief:   Editorial brief text describing pastoral burden and theological lane.
        llm:               Optional LLMClient override (uses cross provider by default).

    Returns:
        Dict with: score (int), status (str), passage_anchored (bool),
        tone_matched (bool), findings (list), priority_fix (str),
        deterministic_findings (list), proposed_code_changes (list).
    """
    if llm is None:
        llm = get_cross_llm_client(worker="prayer_writer")

    deterministic = evaluate_prayer_section(
        prayer_text,
        passage_reference=passage_reference,
        passage_text=passage_text,
        editorial_brief=editorial_brief,
    )
    findings = list(deterministic.get("findings") or [])
    findings_text = "\n".join(f"- {f}" for f in findings) if findings else "No heuristic findings."

    prompt = _PRAYER_TRAINER_PROMPT.format(
        passage_reference=passage_reference,
        passage_text=passage_text[:400],
        editorial_brief=editorial_brief[:400] if editorial_brief else "(not provided)",
        prayer_text=prayer_text,
        findings_text=findings_text,
    )

    raw = llm.generate(prompt)
    result = _parse_prayer_trainer_response(raw)

    score = max(0, min(100, int(result.get("score") or 0)))
    status = "pass" if score >= 80 else "revise" if score >= 60 else "fail"

    return {
        "score": score,
        "status": status,
        "passage_anchored": bool(result.get("passage_anchored")),
        "tone_matched": bool(result.get("tone_matched")),
        "findings": result.get("findings") or [],
        "priority_fix": result.get("priority_fix") or "",
        "deterministic_findings": findings,
        "proposed_code_changes": result.get("proposed_code_changes") or [],
    }
