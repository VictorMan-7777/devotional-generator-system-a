"""SAMPLE_BOOK: a complete DevotionalBook fixture for Phase 002 rendering tests.

Structure:
  - 7 DailyDevotional entries (days 1–7)
  - Days 1–5: standard six sections, no sending_prompt, no day7
  - Day 6: six sections + sending_prompt (Day 6 bridge)
  - Day 7: six sections + day7 (Sunday integration page)

Expected content_pages from DocumentRenderer.render(SAMPLE_BOOK, publish-ready):
  9 pages = 7 day pages + 1 Day 7 integration page + 1 offer page
"""

from datetime import datetime

from src.models.devotional import (
    ActionStepsSection,
    BeStillSection,
    Day7Section,
    DailyDevotional,
    DevotionalBook,
    DevotionalInput,
    ExpositionSection,
    OutputMode,
    PrayerSection,
    ScriptureSection,
    SendingPromptSection,
    TimelessWisdomSection,
)

_NOW = datetime(2026, 2, 24, 12, 0, 0)

# Repeated paragraph to satisfy 500–700 word target for exposition text.
_EXPOSITION_PARA = (
    "The grace of God reaches into the ordinary moments of life, transforming them "
    "into sacred encounters. When we open ourselves to receive what God is offering, "
    "we discover that the kingdom is not distant but close — closer than our next "
    "breath, nearer than our own heartbeat. This is not a truth to be grasped by "
    "intellectual effort alone; it must be received by the whole person. "
)
_EXPOSITION_TEXT = _EXPOSITION_PARA * 8  # ~560 words

# Repeated sentence to satisfy 120–200 word target for prayer text.
_PRAYER_PARA = (
    "Father, thank you for your unfailing grace that meets me here. "
    "Lead me into the truth that sets me free. "
    "Let your Spirit guide every step I take today. "
)
_PRAYER_TEXT = _PRAYER_PARA * 6  # ~135 words


def _wisdom(author: str) -> TimelessWisdomSection:
    return TimelessWisdomSection(
        quote_text=f"The path of wisdom is walked one faithful step at a time. — {author}",
        author=author,
        source_title="Reflections on the Journey",
        publication_year=1985,
        page_or_url="p. 47",
        public_domain=False,
        verification_status="catalog_verified",
    )


def _scripture(reference: str, text: str) -> ScriptureSection:
    return ScriptureSection(
        reference=reference,
        text=text,
        translation="NASB",
        retrieval_source="bolls_life",
        verification_status="bolls_life_verified",
    )


def _exposition() -> ExpositionSection:
    return ExpositionSection(
        text=_EXPOSITION_TEXT,
        word_count=560,
        grounding_map_id="",
    )


def _be_still() -> BeStillSection:
    return BeStillSection(
        prompts=[
            "Sit quietly for two minutes before reading further.",
            "What word or phrase from today's scripture stays with you?",
            "Offer that word back to God in silence.",
        ]
    )


def _action_steps() -> ActionStepsSection:
    return ActionStepsSection(
        items=[
            "Choose one person today and offer a word of encouragement.",
            "Set aside ten minutes this evening for quiet reflection.",
        ],
        connector_phrase="As you move through this day:",
    )


def _prayer() -> PrayerSection:
    return PrayerSection(
        text=_PRAYER_TEXT,
        word_count=135,
        prayer_trace_map_id="",
    )


def _make_day(
    day_number: int,
    *,
    sending_prompt: SendingPromptSection | None = None,
    day7: Day7Section | None = None,
) -> DailyDevotional:
    authors = [
        "Thomas à Kempis",
        "Oswald Chambers",
        "C.S. Lewis",
        "Julian of Norwich",
        "Henri Nouwen",
        "A.W. Tozer",
        "Teresa of Ávila",
    ]
    scriptures = [
        ("Psalm 46:10", "Cease striving and know that I am God."),
        ("Romans 8:15", "For you have not received a spirit of slavery leading to fear again, "
                        "but you have received a spirit of adoption as sons."),
        ("Philippians 4:7", "And the peace of God, which surpasses all comprehension, "
                            "will guard your hearts and your minds in Christ Jesus."),
        ("Isaiah 40:31", "Yet those who wait for the LORD will gain new strength; "
                         "they will mount up with wings like eagles."),
        ("John 15:5", "I am the vine, you are the branches; he who abides in Me "
                      "and I in him, he bears much fruit."),
        ("Matthew 11:28", "Come to Me, all who are weary and heavy-laden, and I will give you rest."),
        ("Lamentations 3:22-23", "The LORD's lovingkindnesses indeed never cease, "
                                 "for His compassions never fail. They are new every morning."),
    ]
    idx = (day_number - 1) % len(authors)
    ref, text = scriptures[idx]
    return DailyDevotional(
        day_number=day_number,
        day_focus=f"Day {day_number} theme — grace in the ordinary",
        timeless_wisdom=_wisdom(authors[idx]),
        scripture=_scripture(ref, text),
        exposition=_exposition(),
        be_still=_be_still(),
        action_steps=_action_steps(),
        prayer=_prayer(),
        sending_prompt=sending_prompt,
        day7=day7,
        created_at=_NOW,
        last_modified=_NOW,
    )


_SENDING_PROMPT = SendingPromptSection(
    text=(
        "Carry this into Sunday: you are not alone. The same grace that met you "
        "in the quiet of this week will meet you in the gathered body. Come expectant. "
        "Come open. Come as you are."
    ),
    word_count=42,
)

_DAY7_SECTION = Day7Section(
    before_service=(
        "Before you leave for worship, hold this week's question in mind: "
        "Where have you most clearly seen the grace of God at work? "
        "Carry that question into the service. Let it be a lens through which "
        "you hear the word proclaimed. You need not have an answer — only the question."
    ),
    after_service_track_a=[
        "How did today's sermon connect with what you have been reading this week?",
        "What image, phrase, or moment from the service will you carry forward?",
        "How does what you heard today deepen or challenge the week's theme?",
    ],
    after_service_track_b=[
        "Where did the sermon take you that surprised you?",
        "Can you hold both threads — the week's theme and today's word — without forcing them together?",
        "What might God be saying through this divergence?",
    ],
    after_service_word_count=155,
)

SAMPLE_BOOK = DevotionalBook(
    id="fixture-sample-book-001",
    input=DevotionalInput(
        topic="Grace in the Ordinary",
        num_days=7,
        scripture_version="NASB",
        output_mode=OutputMode.PUBLISH_READY,
        title="Grace in the Ordinary: A Seven-Day Devotional",
    ),
    days=[
        _make_day(1),
        _make_day(2),
        _make_day(3),
        _make_day(4),
        _make_day(5),
        _make_day(6, sending_prompt=_SENDING_PROMPT),
        _make_day(7, day7=_DAY7_SECTION),
    ],
    series_id="fixture-series-001",
    volume_number=1,
)
