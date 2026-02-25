"""generators.py — Phase 004.D section generator protocol and mock implementations.

Deterministic mock generators only. No LLM calls. No RAG.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.models.devotional import (
    ActionStepsSection,
    BeStillSection,
    DailyDevotional,
    ExpositionSection,
    PrayerSection,
    ScriptureSection,
    TimelessWisdomSection,
)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class SectionGeneratorInterface(Protocol):
    def generate_day(
        self,
        topic: str,
        day_number: int,
        attempt_number: int = 1,
    ) -> DailyDevotional: ...


# ---------------------------------------------------------------------------
# Fixed text blocks — validated against Phase 004 word-count and voice rules
# ---------------------------------------------------------------------------

# 550 neutral theological words. No "you" or "your". 11 groups × 50 = 550.
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

# Be Still prompts: 3 prompts, prompt[1] contains "your" (second-person required).
_BE_STILL_PROMPTS: list[str] = [
    "Sit in silence and reflect on this passage.",
    "What is stirring within your heart today?",
    "Rest in this stillness before moving on.",
]

# 100-word text for FailFirstMockGenerator attempt 1 (triggers EXPOSITION_WORD_COUNT fail).
_FAIL_EXPOSITION_TEXT: str = " ".join(["grace"] * 100)


# ---------------------------------------------------------------------------
# MockSectionGenerator
# ---------------------------------------------------------------------------


class MockSectionGenerator:
    """Produces DailyDevotionals that pass all Phase 004 validators.

    Sections default to SectionApprovalStatus.PENDING (model default).
    quote_text is unique per day_number to prevent registry duplicate errors.
    """

    def generate_day(
        self,
        topic: str,
        day_number: int,
        attempt_number: int = 1,
    ) -> DailyDevotional:
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
                grounding_map_id="",
            ),
            be_still=BeStillSection(
                prompts=_BE_STILL_PROMPTS,
            ),
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


# ---------------------------------------------------------------------------
# FailFirstMockGenerator (test-only)
# ---------------------------------------------------------------------------


class FailFirstMockGenerator:
    """Test-only generator.

    attempt_number == 1 → exposition has 100 words → fails EXPOSITION_WORD_COUNT.
    attempt_number == 2 → delegates to MockSectionGenerator (all validators pass).
    """

    def generate_day(
        self,
        topic: str,
        day_number: int,
        attempt_number: int = 1,
    ) -> DailyDevotional:
        if attempt_number != 1:
            return MockSectionGenerator().generate_day(topic, day_number, attempt_number)

        now = datetime.utcnow()
        return DailyDevotional(
            day_number=day_number,
            timeless_wisdom=TimelessWisdomSection(
                quote_text=f"A quote for testing. Day {day_number}",
                author="Test Author",
                source_title="Test Source",
                page_or_url="p.1",
                public_domain=True,
                verification_status="catalog_verified",
            ),
            scripture=ScriptureSection(
                reference="John 3:16",
                text="For God so loved the world.",
                translation="NASB",
                retrieval_source="operator_import",
                verification_status="catalog_verified",
            ),
            exposition=ExpositionSection(
                text=_FAIL_EXPOSITION_TEXT,  # 100 words — below 500 minimum
                word_count=100,
                grounding_map_id="",
            ),
            be_still=BeStillSection(
                prompts=_BE_STILL_PROMPTS,
            ),
            action_steps=ActionStepsSection(
                items=["Practice gratitude each day."],
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
