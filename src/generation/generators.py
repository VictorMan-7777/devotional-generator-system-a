"""generators.py — Phase 004.D section generator protocol and mock implementations.

Deterministic mock generators only. No LLM calls. No RAG.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from src.generation.editorial import EditorialDayBrief, build_editorial_day_brief
from src.models.devotional import (
    ActionStepsSection,
    BeStillSection,
    DailyDevotional,
    ExpositionSection,
    PrayerSection,
    ScriptureSection,
    TimelessWisdomSection,
)
from src.models.pipeline import PassageResourceBundle


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class SectionGeneratorInterface(Protocol):
    def build_editorial_brief(
        self,
        topic: str,
        day_number: int,
        scripture_reference: str | None = None,
        study_window_reference: str | None = None,
        passage_resources: PassageResourceBundle | None = None,
    ) -> EditorialDayBrief: ...

    def generate_day(
        self,
        topic: str,
        day_number: int,
        attempt_number: int = 1,
        scripture_reference: str | None = None,
        forbidden_quote_texts: set[str] | None = None,
        editorial_brief: EditorialDayBrief | None = None,
        passage_resources: PassageResourceBundle | None = None,
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
# 100-word text for FailFirstMockGenerator attempt 1 (triggers EXPOSITION_WORD_COUNT fail).
_FAIL_EXPOSITION_TEXT: str = " ".join(["grace"] * 100)


def _expand_to_word_count(sentences: list[str], target_words: int) -> str:
    words: list[str] = []
    idx = 0
    while len(words) < target_words:
        sentence = sentences[idx % len(sentences)]
        words.extend(sentence.split())
        idx += 1
    return " ".join(words[:target_words])


def _scripture_for_day(scripture_reference: str | None, day_number: int) -> tuple[str, str]:
    if scripture_reference and scripture_reference.strip():
        base = scripture_reference.strip()
        return (
            f"{base} (Day {day_number})",
            (
                f"Selected passage for day {day_number} from {base}. "
                "Read the referenced verses in your primary Bible text for full context."
            ),
        )
    return ("Lamentations 3:22", "The steadfast love of the Lord never ceases.")


def _be_still_prompts(topic: str, reference: str, day_number: int) -> list[str]:
    return [
        f"Sit quietly with {reference} for two minutes and notice what {topic} requires on day {day_number}.",
        f"What part of {reference} is stirring your heart or challenging your habits today?",
        "Answer God with one honest sentence of trust before you move on.",
    ]


def _action_steps(topic: str, reference: str, day_number: int) -> list[str]:
    action_sets = [
        [
            f"Write one sentence naming how {reference} reframes {topic} for today.",
            "Choose one ordinary task and do it with patience instead of hurry.",
        ],
        [
            f"Pause before one decision today and ask how {reference} should shape your response.",
            "Offer one concrete act of service that matches this day's emphasis.",
        ],
        [
            f"Confess one place where you resisted the truth highlighted in {reference}.",
            "End the day by recording one evidence of grace you noticed in ordinary life.",
        ],
    ]
    return action_sets[(day_number - 1) % len(action_sets)]


def _day_emphasis(day_number: int) -> str:
    emphases = [
        "repentance",
        "steadfast trust",
        "patient obedience",
        "truthful speech",
        "humble service",
        "restful faith",
        "enduring hope",
    ]
    return emphases[(day_number - 1) % len(emphases)]


def _prayer_text(topic: str, reference: str, day_number: int) -> str:
    emphasis = _day_emphasis(day_number)
    sentences = [
        f"Father, thank You for speaking through {reference} on day {day_number}.",
        f"Teach us to receive the truth about {topic} with humility and {emphasis}.",
        "Keep our hearts from drifting into distraction, pride, or anxious control.",
        "Let this passage shape our speech, work, rest, and love for neighbor today.",
        "Grant repentance where we resist You and gratitude where we see Your mercy.",
        f"Make our obedience steady, truthful, and marked by {emphasis} because Your word has met us here.",
    ]
    return _expand_to_word_count(sentences, target_words=150)


# ---------------------------------------------------------------------------
# MockSectionGenerator
# ---------------------------------------------------------------------------


class MockSectionGenerator:
    """Produces DailyDevotionals that pass all Phase 004 validators.

    Sections default to SectionApprovalStatus.PENDING (model default).
    quote_text is unique per day_number to prevent registry duplicate errors.
    """

    def build_editorial_brief(
        self,
        topic: str,
        day_number: int,
        scripture_reference: str | None = None,
        study_window_reference: str | None = None,
        passage_resources: PassageResourceBundle | None = None,
    ) -> EditorialDayBrief:
        window_ref, scripture_text = _scripture_for_day(
            study_window_reference or scripture_reference, day_number
        )
        key_ref, _ = _scripture_for_day(scripture_reference, day_number)
        return build_editorial_day_brief(
            day_number=day_number,
            scripture_reference=key_ref,
            scripture_text=scripture_text,
            study_window_reference=study_window_reference or window_ref,
            passage_resources=passage_resources,
        )

    def generate_day(
        self,
        topic: str,
        day_number: int,
        attempt_number: int = 1,
        scripture_reference: str | None = None,
        forbidden_quote_texts: set[str] | None = None,
        editorial_brief: EditorialDayBrief | None = None,
        passage_resources: PassageResourceBundle | None = None,
    ) -> DailyDevotional:
        now = datetime.now(timezone.utc)
        ref, scripture_text = _scripture_for_day(scripture_reference, day_number)
        emphasis = _day_emphasis(day_number)
        brief = editorial_brief or self.build_editorial_brief(
            topic,
            day_number,
            scripture_reference=scripture_reference,
            passage_resources=passage_resources,
        )
        exposition = _expand_to_word_count(
            [
                (
                    f"{brief.scripture_reference} brings {brief.pastoral_burden} into focus for day {day_number}. "
                    f"The passage in {ref} reveals that God forms a life of {emphasis}, inviting trust rather than anxiety."
                ),
                (
                    f"This context calls the reader to receive identity as gift, not achievement. "
                    f"The text grounds obedience in grace and directs attention to God's character through {emphasis}."
                ),
                (
                    "Because the Lord is faithful, daily decisions can be shaped by worship, truth, "
                    f"and practical love for neighbor in ordinary moments marked by {emphasis}."
                ),
                (
                    "The bridge to application is not self-reliance but response to what God has "
                    f"already spoken and accomplished, especially in the ordinary work of {emphasis}."
                ),
            ],
            target_words=550,
        )
        return DailyDevotional(
            day_number=day_number,
            day_focus=brief.day_title,
            timeless_wisdom=TimelessWisdomSection(
                quote_text=(
                    f"The steadfast love of the Lord endures forever. Day {day_number}"
                ),
                author="Charles Spurgeon",
                source_title="Morning and Evening",
                page_or_url="p.1",
                citation_locator="p.1",
                public_domain=True,
                verification_status="catalog_verified",
            ),
            scripture=ScriptureSection(
                reference=ref,
                text=scripture_text,
                translation="NASB",
                retrieval_source="operator_import",
                verification_status="catalog_verified",
            ),
            exposition=ExpositionSection(
                text=exposition,
                word_count=550,
                grounding_map_id="",
            ),
            be_still=BeStillSection(
                prompts=_be_still_prompts(topic, ref, day_number),
            ),
            action_steps=ActionStepsSection(
                items=_action_steps(topic, ref, day_number),
                connector_phrase=f"Because {ref} addresses {topic} today:",
            ),
            prayer=PrayerSection(
                text=_prayer_text(topic, ref, day_number),
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
        scripture_reference: str | None = None,
        forbidden_quote_texts: set[str] | None = None,
        passage_resources: PassageResourceBundle | None = None,
    ) -> DailyDevotional:
        if attempt_number != 1:
            return MockSectionGenerator().generate_day(
                topic,
                day_number,
                attempt_number,
                scripture_reference=scripture_reference,
                forbidden_quote_texts=forbidden_quote_texts,
                passage_resources=passage_resources,
            )

        now = datetime.now(timezone.utc)
        return DailyDevotional(
            day_number=day_number,
            day_focus=f"Day {day_number} - {topic}",
            timeless_wisdom=TimelessWisdomSection(
                quote_text=f"A quote for testing. Day {day_number}",
                author="Test Author",
                source_title="Test Source",
                page_or_url="p.1",
                citation_locator="p.1",
                public_domain=True,
                verification_status="catalog_verified",
            ),
            scripture=ScriptureSection(
                reference=scripture_reference or "John 3:16",
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
                prompts=_be_still_prompts(topic, scripture_reference or "John 3:16", day_number),
            ),
            action_steps=ActionStepsSection(
                items=[f"Name one way {topic} should reshape your next decision."],
                connector_phrase=f"Because {scripture_reference or 'John 3:16'} speaks today:",
            ),
            prayer=PrayerSection(
                text=_prayer_text(topic, scripture_reference or "John 3:16", day_number),
                word_count=150,
                prayer_trace_map_id="",
            ),
            sending_prompt=None,
            day7=None,
            created_at=now,
            last_modified=now,
        )
