"""llm_library_trainer_core.py — LLM-backed evaluation of research librarian reading notes.

The library trainer uses Claude or Codex to read research librarian notes and evaluate
whether they demonstrate accomplished behavior: identifying resource strengths and limits,
using the shelf before escalating, and writing notes that improve future requests.

Provider is configured via DEVG_LLM_PROVIDER (default: claude).
Worker override: DEVG_LLM_LIBRARY_TRAINER.
"""
from __future__ import annotations

import json
import re
from typing import Any

from src.llm.interfaces import LLMClient
from src.llm.router import get_llm_client


_NOTE_REVIEW_PROMPT_TEMPLATE = """\
You are an expert library trainer for a devotional research system.

Your task: Evaluate the following research librarian's reading note for quality and judgment.

RESOURCE: {resource_title}
PASSAGE CONTEXT: {passage_reference}

READING NOTE:
{note_text}

EVALUATION RUBRIC:
1. Does the note explain what this resource is genuinely useful for — not just \
   what the catalog entry says?
2. Does it identify specific strengths (what the resource does well for this passage) \
   AND specific limits (where it falls short)?
3. Would this note help the next researcher answer a similar passage request more intelligently?
4. Is this accomplished behavior: did the librarian engage with the actual resource \
   rather than just the catalog metadata?
5. Is there evidence the librarian used the shelf before escalating to acquisition?

ACCOMPLISHED vs BEGINNER:
- BEGINNER: Vague, generic, could apply to any resource; escalates without checking shelf.
- ACCOMPLISHED: Specific, passage-aware, identifies strengths and limits, escalates \
  only when shelf genuinely cannot serve the need.

Respond ONLY with a valid JSON object. No preamble or explanation outside the JSON.

{{
  "decision": "<accepted|revise>",
  "score": <integer 0-100>,
  "maturity_level": "<accomplished|beginner>",
  "rationale": "<specific explanation of the decision>",
  "specific_feedback": "<concrete suggestion for improvement if revise, or confirmation of what was done well>"
}}

Decision: "accepted" if the note demonstrates accomplished behavior (score >= 70); \
"revise" if too vague, generic, or missing key judgment (score < 70).
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
        "decision": "revise",
        "score": 0,
        "maturity_level": "beginner",
        "rationale": f"LLM returned an unparseable response: {raw[:200]}",
        "specific_feedback": "Re-run library trainer evaluation and inspect LLM output format.",
    }


def evaluate_reading_note_with_llm(
    note_text: str,
    *,
    resource_title: str,
    passage_reference: str,
    llm: LLMClient | None = None,
) -> dict[str, Any]:
    """Evaluate a research librarian reading note via LLM.

    The LLM reads the note and provides expert assessment of whether the
    librarian demonstrated accomplished shelf-research behavior.

    Args:
        note_text: The reading note text to evaluate.
        resource_title: Title of the resource the note covers.
        passage_reference: The passage the note was prepared for.
        llm: Optional LLMClient override (uses DEVG_LLM_LIBRARY_TRAINER by default).

    Returns:
        Dict with keys: decision (accepted|revise), score (int),
        maturity_level (str), rationale (str), specific_feedback (str).
    """
    if llm is None:
        llm = get_llm_client(worker="library_trainer")

    prompt = _NOTE_REVIEW_PROMPT_TEMPLATE.format(
        resource_title=(resource_title or "Unknown Resource"),
        passage_reference=(passage_reference or "Unspecified Passage"),
        note_text=(note_text or "").strip()[:2000],
    )

    raw = llm.generate(prompt)
    result = _parse_llm_response(raw)

    # Normalize decision based on score
    score = int(result.get("score") or 0)
    result["score"] = score
    result["decision"] = "accepted" if score >= 70 else "revise"

    return result


def evaluate_notes_batch(
    notes: list[dict[str, Any]],
    *,
    llm: LLMClient | None = None,
) -> list[dict[str, Any]]:
    """Evaluate a batch of reading notes, each as a dict with note_text, resource_title, passage_reference.

    Returns a list of evaluation results in the same order as the input notes.
    Silently skips notes with missing text rather than failing the whole batch.
    """
    results: list[dict[str, Any]] = []
    for note in notes:
        note_text = str(note.get("note_text") or "").strip()
        if not note_text:
            results.append({
                "decision": "revise",
                "score": 0,
                "maturity_level": "beginner",
                "rationale": "Note text was empty — no content to evaluate.",
                "specific_feedback": "Supply actual note content before requesting evaluation.",
            })
            continue
        result = evaluate_reading_note_with_llm(
            note_text,
            resource_title=str(note.get("resource_title") or "Unknown Resource"),
            passage_reference=str(note.get("passage_reference") or "Unspecified Passage"),
            llm=llm,
        )
        results.append(result)
    return results
