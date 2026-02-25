"""real_section_generator.py — Phase 011 DeterministicRealSectionGenerator.

No LLM. Uses ExpositionRAG seed excerpts + GroundingMapBuilder + GroundingMapStore
to produce ExpositionSection artifacts with a saved, retrievable GroundingMap.

Purpose: prove end-to-end artifact lifecycle —
  generator → save → orchestrator auto-resolves → validation runs → audit passes.

Contract:
- No LLM calls, no network calls, no embeddings.
- Deterministic: identical (topic, day_number) inputs produce the same grounding_map_id.
- Side effect: saves GroundingMap to GroundingMapStore on each call (idempotent).
- Returns a DailyDevotional whose exposition.grounding_map_id is truthy.
"""
from __future__ import annotations

from datetime import datetime

from src.grounding_store.id_policy import create_grounding_map_id
from src.grounding_store.store import GroundingMapStore
from src.models.devotional import (
    ActionStepsSection,
    BeStillSection,
    DailyDevotional,
    ExpositionSection,
    PrayerSection,
    ScriptureSection,
    TimelessWisdomSection,
)
from src.rag.exposition import ExpositionRAG
from src.rag.grounding import GroundingMapBuilder

# ---------------------------------------------------------------------------
# Fixed text blocks — validated against Phase 004 word-count and voice rules.
# 550 neutral theological words; no "you" or "your".
# ---------------------------------------------------------------------------
_WORDS_550: list[str] = (
    ["grace"] * 50
    + ["mercy"] * 50
    + ["faith"] * 50
    + ["hope"] * 50
    + ["love"] * 50
    + ["peace"] * 50
    + ["wisdom"] * 50
    + ["strength"] * 50
    + ["light"] * 50
    + ["truth"] * 50
    + ["spirit"] * 50
)
_EXPOSITION_TEXT: str = " ".join(_WORDS_550)

# 150 words starting with "Father," for Trinity address. 1 + 149 = 150.
_PRAYER_TEXT: str = "Father, " + " ".join(["grace"] * 149)

# Be Still prompts: prompt[1] contains "your" (second-person required for be_still).
_BE_STILL_PROMPTS: list[str] = [
    "Sit in silence and reflect on this passage.",
    "What is stirring within your heart today?",
    "Rest in this stillness before moving on.",
]


class DeterministicRealSectionGenerator:
    """No-LLM section generator that produces exposition artifacts with saved GroundingMaps.

    Uses ExpositionRAG seed excerpts for all 4 paragraph grounding slots, then
    persists a GroundingMap to GroundingMapStore before returning the DailyDevotional.

    Grounding slot assignment:
        Paragraph 1 (declaration): first available excerpt (from context or theological set)
        Paragraph 2 (context):     full context excerpt set from ExpositionRAG
        Paragraph 3 (theological): full theological excerpt set from ExpositionRAG
        Paragraph 4 (bridge):      first available excerpt (same as paragraph 1)

    The grounding_map_id is deterministic: ``create_grounding_map_id(exposition_id)``
    where ``exposition_id = "expo-{topic}-day{day_number}"``.

    Side effect: saves GroundingMap to ``GroundingMapStore(GroundingMapStore.DEFAULT_ROOT)``
    on each call.  Because the id is deterministic, repeated calls overwrite rather
    than accumulate. Tests should monkeypatch ``GroundingMapStore.DEFAULT_ROOT`` to
    ``tmp_path`` to avoid writing to the canonical data directory.
    """

    def generate_day(
        self,
        topic: str,
        day_number: int,
        attempt_number: int = 1,
    ) -> DailyDevotional:
        exposition_id = f"expo-{topic}-day{day_number}"
        grounding_map_id = create_grounding_map_id(exposition_id)

        # ----------------------------------------------------------------
        # Retrieve excerpts from seed file.
        # ----------------------------------------------------------------
        rag = ExpositionRAG()
        excerpts_2 = rag.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="",
            topic=topic,
            source_types=["commentary"],
        )
        excerpts_3 = rag.retrieve_for_paragraph(
            paragraph_type="theological",
            passage_reference="",
            topic=topic,
            source_types=["commentary"],
        )

        # Paragraphs 1 and 4 reuse the first available excerpt from either set.
        first_excerpt = (excerpts_2 + excerpts_3)[0:1]

        paragraph_excerpts = {
            1: first_excerpt,
            2: excerpts_2,
            3: excerpts_3,
            4: first_excerpt,
        }

        # ----------------------------------------------------------------
        # Build GroundingMap, assign deterministic id, persist.
        # ----------------------------------------------------------------
        gm = GroundingMapBuilder().build(exposition_id, paragraph_excerpts)
        gm = gm.model_copy(update={"id": grounding_map_id})

        store = GroundingMapStore(root_dir=GroundingMapStore.DEFAULT_ROOT)
        store.save(gm)

        # ----------------------------------------------------------------
        # Assemble DailyDevotional.
        # ----------------------------------------------------------------
        now = datetime.utcnow()
        return DailyDevotional(
            day_number=day_number,
            timeless_wisdom=TimelessWisdomSection(
                quote_text=(
                    f"The steadfast love of the Lord endures forever. Day {day_number}"
                ),
                author="Charles Spurgeon",
                source_title="Morning and Evening",
                page_or_url="p.1",
                public_domain=True,
                verification_status="catalog_verified",
            ),
            scripture=ScriptureSection(
                reference="Lamentations 3:22",
                text="The steadfast love of the Lord never ceases.",
                translation="NASB",
                retrieval_source="operator_import",
                verification_status="catalog_verified",
            ),
            exposition=ExpositionSection(
                text=_EXPOSITION_TEXT,
                word_count=550,
                grounding_map_id=grounding_map_id,
            ),
            be_still=BeStillSection(prompts=_BE_STILL_PROMPTS),
            action_steps=ActionStepsSection(
                items=[
                    "Spend five minutes in silent prayer each morning.",
                    "Offer one act of kindness to someone today.",
                ],
                connector_phrase="This week, practice this:",
            ),
            prayer=PrayerSection(
                text=_PRAYER_TEXT,
                word_count=150,
                prayer_trace_map_id="",
            ),
            sending_prompt=None,
            day7=None,
            created_at=now,
            last_modified=now,
        )
