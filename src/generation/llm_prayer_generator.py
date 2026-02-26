"""llm_prayer_generator.py — Phase 013 CP1 LLM-backed prayer generator.

Generates PrayerSection.text via a single LLM call, grounded by
deterministic element classification and a persisted PrayerTraceMap artifact.

Contract:
- LLM is called exactly once per generate_prayer() call.
- Elements are parsed deterministically: text.split("\n"), filter empty lines.
- Guard raises ValueError if no parseable elements are produced.
- PrayerTraceMap is built and saved before returning PrayerSection.
- prayer_trace_map_id is always truthy on the returned PrayerSection.
- No network calls beyond the injected llm.generate().
- No randomness. No embeddings. No vector DB.

Element classification (module-level, deterministic):
    scripture:  element contains \\d+:\\d+ (chapter:verse reference)
    exposition: element contains "exposition" (case-insensitive)
    be_still:   all other elements
"""
from __future__ import annotations

import re
from typing import Optional

from src.llm.interfaces import LLMClient
from src.models.artifacts import PrayerTraceMap, PrayerTraceMapEntry
from src.models.devotional import PrayerSection
from src.prayer_trace_store.id_policy import create_prayer_trace_map_id
from src.prayer_trace_store.store import PrayerTraceMapStore

# ---------------------------------------------------------------------------
# Element classifiers
# ---------------------------------------------------------------------------

_SCRIPTURE_REF = re.compile(r"\d+:\d+")


def _classify_source_type(element: str) -> str:
    if _SCRIPTURE_REF.search(element):
        return "scripture"
    if "exposition" in element.lower():
        return "exposition"
    return "be_still"


def _classify_source_reference(element: str, passage_reference: str) -> str:
    if _SCRIPTURE_REF.search(element):
        return passage_reference
    if "exposition" in element.lower():
        return "exposition"
    return "be_still"


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _build_prayer_prompt(
    topic: str,
    passage_reference: str,
    exposition_text: str,
    be_still_prompts: list[str],
) -> str:
    lines: list[str] = []

    lines.append(f"TOPIC: {topic}")
    lines.append(f"PASSAGE: {passage_reference}")
    lines.append("")
    lines.append("EXPOSITION (first 500 chars):")
    lines.append(exposition_text[:500])
    lines.append("")
    lines.append("BE STILL PROMPTS:")
    for prompt in be_still_prompts:
        lines.append(f"- {prompt}")
    lines.append("")
    lines.append(
        "INSTRUCTION: Structure the prayer into clearly separable elements "
        "(one per line). Each petition must be grounded in scripture, "
        "exposition, or be_still."
    )
    lines.append("")
    lines.append("REQUIREMENTS:")
    lines.append("- 120\u2013200 words total")
    lines.append("- Address at least one Trinity name (Father, Jesus, Lord, Spirit, God)")
    lines.append("- One petition per line")
    lines.append("- For scripture petitions include passage reference as Chapter:Verse")
    lines.append('- For exposition petitions include the word "exposition"')

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class LLMPrayerGenerator:
    """LLM-backed prayer generator with deterministic element classification.

    Parses prayer text into non-empty line elements, classifies each via
    deterministic regex rules, persists a PrayerTraceMap artifact, then
    returns PrayerSection with a truthy prayer_trace_map_id.

    Args:
        llm:   Injectable LLMClient. Must not be called more than once
               per generate_prayer() invocation.
        store: Optional PrayerTraceMapStore. If None, the store is
               instantiated at call-time using
               PrayerTraceMapStore.DEFAULT_ROOT (the class attribute),
               which is monkeypatchable in tests.
    """

    def __init__(
        self,
        llm: LLMClient,
        store: Optional[PrayerTraceMapStore] = None,
    ) -> None:
        self._llm = llm
        self._store = store

    def generate_prayer(
        self,
        prayer_id: str,
        topic: str,
        passage_reference: str,
        exposition_text: str,
        be_still_prompts: list[str],
    ) -> PrayerSection:
        """Generate a PrayerSection backed by a single LLM call.

        Steps:
          1. Build a prompt from topic, passage, exposition, and be_still prompts.
          2. Call llm.generate() exactly once to obtain prayer text.
          3. Parse text into non-empty line elements.
          4. Guard: raise ValueError if no parseable elements are produced.
          5. Classify each element deterministically (scripture/exposition/be_still).
          6. Build a PrayerTraceMap with a deterministic id and persist it.
          7. Return PrayerSection with truthy prayer_trace_map_id.

        Args:
            prayer_id:          Stable identifier for this prayer
                                (e.g. "prayer-grace-day1"). Used to derive
                                the deterministic prayer_trace_map_id.
            topic:              Devotional topic string.
            passage_reference:  Scripture passage reference (e.g. "Romans 8:28").
            exposition_text:    Text of the associated ExpositionSection.
                                First 500 chars are included in the prompt.
            be_still_prompts:   Ordered list of be-still prompt strings.

        Returns:
            PrayerSection with text from the LLM, computed word_count,
            and a truthy prayer_trace_map_id referencing the saved artifact.

        Raises:
            ValueError: if the LLM response produces no parseable line elements.
        """
        # ------------------------------------------------------------------
        # Step 1 — Build prompt.
        # ------------------------------------------------------------------
        prompt = _build_prayer_prompt(
            topic, passage_reference, exposition_text, be_still_prompts
        )

        # ------------------------------------------------------------------
        # Step 2 — Single LLM call.
        # ------------------------------------------------------------------
        text = self._llm.generate(prompt)

        # ------------------------------------------------------------------
        # Step 3 — Parse elements.
        # ------------------------------------------------------------------
        elements = [line.strip() for line in text.split("\n") if line.strip()]

        # ------------------------------------------------------------------
        # Step 4 — Guard: must have at least one parseable element.
        # ------------------------------------------------------------------
        if not elements:
            raise ValueError("Prayer text produced no parseable elements")

        # ------------------------------------------------------------------
        # Step 5 — Classify each element deterministically.
        # ------------------------------------------------------------------
        entries = [
            PrayerTraceMapEntry(
                element_text=el,
                source_type=_classify_source_type(el),
                source_reference=_classify_source_reference(el, passage_reference),
            )
            for el in elements
        ]

        # ------------------------------------------------------------------
        # Step 6 — Build PrayerTraceMap, assign deterministic id, persist.
        # ------------------------------------------------------------------
        ptm_id = create_prayer_trace_map_id(prayer_id)
        ptm = PrayerTraceMap(id=ptm_id, prayer_id=prayer_id, entries=entries)

        active_store = (
            self._store
            if self._store is not None
            else PrayerTraceMapStore(root_dir=PrayerTraceMapStore.DEFAULT_ROOT)
        )
        active_store.save(ptm)

        # ------------------------------------------------------------------
        # Step 7 — Return PrayerSection.
        # ------------------------------------------------------------------
        return PrayerSection(
            text=text,
            word_count=len(text.split()),
            prayer_trace_map_id=ptm_id,
        )
