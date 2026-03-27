"""llm_research_librarian_core.py — LLM-backed seminary research librarian.

The research librarian is the intelligence layer between the RAG catalog and
the workers who depend on it.  It acts as a seminary reference librarian:
knowing the collection deeply, understanding which resources serve which
passage genres and theological themes, annotating why each resource is
relevant to the specific passage, and identifying gaps that require escalation.

Provider is configured via DEVG_LLM_PROVIDER (default: claude).
Worker override: DEVG_LLM_RESEARCH_LIBRARIAN.
"""
from __future__ import annotations

import json
import re
from typing import Any

from src.llm.router import get_llm_client
from src.llm.interfaces import LLMClient


_SEMINARY_LIBRARIAN_PROMPT = """\
You are the research librarian for a devotional publishing system. Your role \
is equivalent to a seminary reference librarian: you know the collection \
deeply, you understand which resources serve which passage genres and \
theological themes, and you curate a precise, well-annotated bundle for \
the exposition writer and the outliner.

PASSAGE: {passage_reference}
TOPIC: {topic}
PASSAGE GENRE: {genre}

YOUR COLLECTION (reading notes — what you know about each resource):
{reading_notes}

RAW CANDIDATE EXCERPTS FROM THE CATALOG ({excerpt_count} excerpts found):
{excerpts}

YOUR TASK:
1. Evaluate whether these excerpts give the exposition writer enough to work \
   with for {passage_reference}.
2. For each resource represented, write a specific annotation explaining \
   exactly why it helps (or does not help) THIS passage — not a generic \
   description of the resource.
3. Identify what is missing: which type of resource would improve the bundle \
   (e.g., "needs original-language word study on the Hebrew of Psalm 23:1", \
   "needs a devotional commentary that handles the Psalm's pastoral imagery").
4. Suggest 1-3 additional search terms that would surface better material \
   from the catalog if the current results are thin.

PASSAGE GENRE GUIDANCE:
- Poetry (Psalms, Proverbs, Song of Solomon): prioritize resources that \
  handle Hebrew poetry, parallelism, and pastoral/wisdom imagery.  \
  Commentaries that treat poetry as didactic prose are less useful.
- Narrative (Genesis–2 Kings, Gospels, Acts): prioritize verse-by-verse \
  historical/contextual commentary.  Matthew Henry and JFB are strong here.
- Epistle (Romans–Jude): prioritize doctrinal/systematic resources and \
  word-study tools.  Strong's, Institutes, Watson are relevant.
- Prophetic (Isaiah–Malachi, Revelation): prioritize commentaries with \
  historical-context depth and Christological awareness.
- Wisdom (Job, Ecclesiastes): prioritize resources that handle theodicy, \
  suffering, and providence.

BUNDLE SUFFICIENCY STANDARD:
- STRONG: 4+ exposition-quality excerpts from at least 2 distinct resources, \
  at least one anchored directly to the passage.
- ADEQUATE: 2–3 exposition excerpts; may need escalation for depth.
- THIN: fewer than 2 exposition excerpts; escalation recommended.

Respond ONLY with a valid JSON object. No preamble or explanation outside the JSON.

{{
  "bundle_assessment": "<strong|adequate|thin>",
  "resource_annotations": [
    {{
      "source_title": "<exact title from excerpts>",
      "author": "<author>",
      "passage_relevance": "<specific note about why this resource helps {passage_reference}>",
      "priority": "<primary|secondary|supplemental>"
    }}
  ],
  "missing_resource_types": ["<type1>", "<type2>"],
  "suggested_search_terms": ["<term1>", "<term2>"],
  "escalation_needed": <true|false>,
  "escalation_rationale": "<why escalation is or is not needed>"
}}
"""


def _detect_genre(reference: str) -> str:
    """Return a broad genre label for a scripture reference."""
    ref = reference.strip().lower()
    poetry = {"psalm", "psalms", "proverbs", "song of solomon", "song of songs", "lamentations"}
    wisdom = {"job", "ecclesiastes"}
    prophetic = {
        "isaiah", "jeremiah", "ezekiel", "daniel", "hosea", "joel", "amos",
        "obadiah", "jonah", "micah", "nahum", "habakkuk", "zephaniah", "haggai",
        "zechariah", "malachi", "revelation",
    }
    epistle = {
        "romans", "1 corinthians", "2 corinthians", "galatians", "ephesians",
        "philippians", "colossians", "1 thessalonians", "2 thessalonians",
        "1 timothy", "2 timothy", "titus", "philemon", "hebrews",
        "james", "1 peter", "2 peter", "1 john", "2 john", "3 john", "jude",
    }
    for book in poetry:
        if book in ref:
            return "Poetry"
    for book in wisdom:
        if book in ref:
            return "Wisdom"
    for book in prophetic:
        if book in ref:
            return "Prophetic"
    for book in epistle:
        if book in ref:
            return "Epistle"
    return "Narrative"


def _parse_llm_response(raw: str) -> dict[str, Any]:
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    return {
        "bundle_assessment": "adequate",
        "resource_annotations": [],
        "missing_resource_types": [],
        "suggested_search_terms": [],
        "escalation_needed": False,
        "escalation_rationale": f"LLM returned unparseable response: {raw[:200]}",
    }


def curate_passage_bundle(
    *,
    passage_reference: str,
    topic: str,
    candidate_excerpts: list[dict[str, Any]],
    reading_note_hints: list[str],
    llm: LLMClient | None = None,
) -> dict[str, Any]:
    """Ask the seminary librarian LLM to evaluate and annotate a passage bundle.

    Args:
        passage_reference: The scripture passage being researched.
        topic: The devotional topic context.
        candidate_excerpts: Raw excerpts from ExpositionRAG, each with
            source_title, author, text, source_type, relevance_score.
        reading_note_hints: One-liner resource memory strings from reading notes.
        llm: Optional LLMClient override.

    Returns:
        Dict with bundle_assessment, resource_annotations, missing_resource_types,
        suggested_search_terms, escalation_needed, escalation_rationale.
    """
    if llm is None:
        llm = get_llm_client(worker="research_librarian")

    genre = _detect_genre(passage_reference)

    reading_notes_text = "\n".join(
        f"- {hint}" for hint in reading_note_hints if hint.strip()
    ) or "(no reading notes available)"

    # Format excerpts concisely — truncate each to 200 chars to stay within context
    excerpt_lines = []
    for i, ex in enumerate(candidate_excerpts[:12], 1):
        title = str(ex.get("source_title") or "Unknown")
        author = str(ex.get("author") or "")
        text = str(ex.get("text") or str(ex.get("excerpt_text") or ""))[:200]
        score = ex.get("relevance_score", 0)
        excerpt_lines.append(
            f"{i}. [{title} / {author}] (score: {score:.2f})\n   {text}"
        )
    excerpts_text = "\n\n".join(excerpt_lines) or "(no excerpts found)"

    prompt = _SEMINARY_LIBRARIAN_PROMPT.format(
        passage_reference=passage_reference,
        topic=topic or passage_reference,
        genre=genre,
        reading_notes=reading_notes_text,
        excerpts=excerpts_text,
        excerpt_count=len(candidate_excerpts),
    )

    raw = llm.generate(prompt)
    return _parse_llm_response(raw)
