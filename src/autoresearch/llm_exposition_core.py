"""llm_exposition_core.py — LLM exposition trainer: evaluates deterministic exposition artifacts.

The exposition writer is a deterministic pipeline worker (real_section_generator.py).
This module provides the LLM TRAINER that reads what the deterministic writer produced
and evaluates it with expert eyes — checking whether the exposition is genuinely
passage-specific or generic devotional filler.

Provider is configured via DEVG_LLM_PROVIDER (default: claude).
Worker override: DEVG_LLM_EXPOSITION_WRITER.

Pass threshold: score >= 80 (out of 100).
"""
from __future__ import annotations

import json
import re
from typing import Any

from src.llm.interfaces import LLMClient
from src.llm.router import get_cross_llm_client, get_llm_client


_GENERIC_SCAFFOLD_PHRASES = (
    "god is faithful",
    "as we trust",
    "let us remember",
    "in our daily lives",
    "day by day",
    "walk with god",
    "god's love for us",
    "in his infinite wisdom",
    "through life's",
    "this passage reminds us",
    "we are reminded",
    "may we",
    "lord, help us",
    "as believers",
    "christian life",
    "spiritual journey",
)

_STOPWORDS = {
    "the", "and", "that", "with", "from", "into", "this", "were", "was", "have",
    "has", "had", "their", "they", "them", "there", "about", "your", "what",
    "you", "when", "while", "would", "could", "should", "among", "during",
    "after", "before", "because", "through", "those", "these", "very", "then",
    "than", "unto", "lord", "god", "also", "will", "shall", "said", "not",
    "but", "for", "all", "are", "him", "his", "her", "its", "who", "which",
}


def _meaningful_tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text or "")
        if token.lower() not in _STOPWORDS and len(token) >= 4
    }


def evaluate_exposition_section(
    text: str,
    *,
    passage_text: str,
    focal_reference: str,
) -> dict[str, Any]:
    """Score an exposition section against the exposition writer rubric.

    Returns:
        dict with keys: status ("pass"/"revise"/"fail"), score (0–100), findings, metrics
    """
    findings: list[str] = []
    score = 100

    words = text.split()
    word_count = len(words)

    # Word count check
    if word_count < 150:
        findings.append(f"Exposition is too short: {word_count} words (minimum 150).")
        score -= 30
    elif word_count < 200:
        findings.append(f"Exposition is below target length: {word_count} words (target 200–600).")
        score -= 15
    elif word_count > 700:
        findings.append(f"Exposition exceeds maximum length: {word_count} words (maximum 700).")
        score -= 10

    # Generic scaffold detection
    lowered_text = text.lower()
    scaffold_count = sum(1 for phrase in _GENERIC_SCAFFOLD_PHRASES if phrase in lowered_text)
    if scaffold_count >= 3:
        findings.append(f"Exposition contains {scaffold_count} generic devotional scaffold phrases.")
        score -= scaffold_count * 6
    elif scaffold_count > 0:
        findings.append(f"Exposition contains {scaffold_count} generic devotional phrase(s).")
        score -= scaffold_count * 4

    # Passage anchoring — key terms from passage text should appear in exposition
    passage_tokens = _meaningful_tokens(passage_text)
    exposition_tokens = _meaningful_tokens(text)
    overlap = len(passage_tokens.intersection(exposition_tokens))
    if overlap == 0:
        findings.append("Exposition shares no meaningful terms with the passage text — not anchored.")
        score -= 25
    elif overlap < 3:
        findings.append(f"Exposition has weak passage anchoring: only {overlap} term(s) shared with the text.")
        score -= 12

    # Focal reference check — exposition should reference or engage the focal verse
    focal_tokens = _meaningful_tokens(focal_reference)
    focal_overlap = len(focal_tokens.intersection(exposition_tokens))
    if focal_tokens and focal_overlap == 0:
        findings.append(f"Exposition does not engage with the focal reference ({focal_reference}).")
        score -= 15

    # Basic readability heuristic — average word length (long words → hard text)
    if words:
        avg_word_len = sum(len(w) for w in words) / len(words)
        if avg_word_len > 7.0:
            findings.append(
                f"Average word length is {avg_word_len:.1f} characters — prose may be too complex for grade 7–8 target."
            )
            score -= 8

    score = max(0, score)
    status = "pass" if score >= 80 else "revise" if score >= 60 else "fail"

    return {
        "status": status,
        "score": score,
        "findings": findings,
        "metrics": {
            "word_count": word_count,
            "scaffold_phrase_count": scaffold_count,
            "passage_term_overlap": overlap,
            "focal_term_overlap": focal_overlap,
        },
    }


# ── LLM Exposition Trainer ────────────────────────────────────────────────────

_EXPOSITION_TRAINER_PROMPT = """\
You are an expert exposition trainer evaluating a devotional exposition paragraph \
produced by a deterministic exposition writer.

Your task: Read the exposition below and evaluate whether it is genuinely \
passage-specific or generic devotional filler. An exposition passes when every \
sentence could only have been written about THIS text.

PASSAGE: {topic}
FOCAL REFERENCE: {focal_reference}

PASSAGE TEXT:
{passage_text}

EXPOSITION TO EVALUATE ({word_count} words):
{exposition_text}

DETERMINISTIC SCORING FINDINGS:
{findings_text}

EVALUATION RUBRIC:
1. Does every sentence draw from THIS specific text, or could it apply to any passage?
2. Does the exposition engage with the focal reference ({focal_reference}) directly?
3. Does it drift into generic devotional clichés ("God is faithful", "walk with God", "let us remember")?
4. Is the prose clear, varied, and appropriately toned for the passage's genre?
5. Does it respect the theological weight and tone of the passage without softening or inflating it?

Respond ONLY with valid JSON. No preamble or explanation outside the JSON.

{{
  "score": <integer 0–100>,
  "status": "<pass|revise|fail>",
  "passage_grounded": <true|false>,
  "generic_phrase_count": <integer>,
  "findings": [
    "<specific observation referencing actual exposition content>"
  ],
  "priority_fix": "<the single most important improvement the exposition writer should make>",
  "proposed_code_changes": [
    {{
      "file_path": "<relative path to the source file that should change, e.g. src/generation/real_section_generator.py>",
      "objective": "<one-line description of the change>",
      "change_description": "<concrete description: what to change, where, and to what>",
      "rationale": "<why this is a structural code problem, not a training problem that repetition would fix>"
    }}
  ]
}}

Score guide: pass >= 80, revise >= 60, fail < 60. Status must match the score.

proposed_code_changes guide: Only populate if you observe a structural pattern that CANNOT be \
fixed by running more training cycles — e.g. a hardcoded template sentence that appears verbatim \
in every output, a repeated closing paragraph, an imported theological concept that has no basis \
in the supplied passage text, or a generation loop that truncates mid-sentence. If the problem is \
a matter of training quality (exposition could improve with better rubric adherence), leave the \
list empty. Name the exact function and describe the concrete change needed.
"""


def _parse_exposition_trainer_response(raw: str) -> dict[str, Any]:
    """Extract and parse JSON from LLM trainer response, with fallback."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {
        "score": 0,
        "status": "revise",
        "passage_grounded": False,
        "generic_phrase_count": 0,
        "findings": [f"Trainer could not parse LLM response: {raw[:200]}"],
        "priority_fix": "Re-run trainer evaluation and inspect LLM output format.",
    }


def build_llm_exposition_trainer_review(
    exposition_text: str,
    *,
    passage_text: str,
    focal_reference: str,
    topic: str = "",
    llm: LLMClient | None = None,
) -> dict[str, Any]:
    """LLM trainer evaluates a deterministic exposition section and provides expert coaching.

    Reads the exposition produced by the deterministic writer and checks whether
    it is passage-specific or generic devotional filler. Returns a scored review
    with specific coaching notes.

    Args:
        exposition_text: The exposition text produced by the deterministic writer.
        passage_text: The scripture text for this day's study window.
        focal_reference: The narrow focal verse reference (e.g. "Ruth 1:16-17").
        topic: The passage topic label.
        llm: Optional LLMClient override (uses DEVG_LLM_EXPOSITION_WRITER by default).

    Returns:
        Dict with: score (int), status (str), passage_grounded (bool),
        generic_phrase_count (int), findings (list), priority_fix (str).
    """
    if llm is None:
        # Trainer deliberately uses the CROSS provider — the AI evaluating exposition
        # must be different from the AI used by any LLM-assisted generation steps.
        llm = get_cross_llm_client(worker="exposition_writer")

    # Run deterministic pre-check to provide findings context for the LLM
    deterministic = evaluate_exposition_section(
        exposition_text,
        passage_text=passage_text,
        focal_reference=focal_reference,
    )
    findings = list(deterministic.get("findings") or [])
    findings_text = "\n".join(f"- {f}" for f in findings) if findings else "No heuristic findings."
    word_count = int(deterministic.get("metrics", {}).get("word_count") or 0)

    prompt = _EXPOSITION_TRAINER_PROMPT.format(
        topic=topic or focal_reference,
        focal_reference=focal_reference,
        passage_text=passage_text[:1200],
        exposition_text=exposition_text[:3000],
        word_count=word_count,
        findings_text=findings_text,
    )

    raw = llm.generate(prompt)
    result = _parse_exposition_trainer_response(raw)

    score = max(0, min(100, int(result.get("score") or 0)))
    if score >= 80:
        status = "pass"
    elif score >= 60:
        status = "revise"
    else:
        status = "fail"

    return {
        "score": score,
        "status": status,
        "passage_grounded": bool(result.get("passage_grounded")),
        "generic_phrase_count": int(result.get("generic_phrase_count") or 0),
        "findings": result.get("findings") or [],
        "priority_fix": result.get("priority_fix") or "",
        "deterministic_findings": findings,
        "proposed_code_changes": result.get("proposed_code_changes") or [],
    }
