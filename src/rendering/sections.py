"""Section-level renderers: DailyDevotional section schemas → List[DocumentBlock].

All renderers are pure functions with no file I/O. They take a section schema object
and return a list of DocumentBlock instances ready for assembly into a DocumentPage.

Reader-facing heading strings are fixed per PRD D016:
  Timeless Wisdom | Scripture Reading | Reflection | Still Before God | Walk It Out | Prayer

Day 7 headings per PRD D056:
  Before the Service | After the Service | Track A / Track B
"""

from typing import List

from src.models.devotional import (
    ActionStepsSection,
    BeStillSection,
    Day7Section,
    ExpositionSection,
    PrayerSection,
    ScriptureSection,
    SendingPromptSection,
    TimelessWisdomSection,
)
from src.models.document import BlockType, DocumentBlock, PageNumberStyle


def _block(
    block_type: BlockType,
    content: str,
    *,
    page_number_style: PageNumberStyle = PageNumberStyle.ARABIC,
    metadata: dict | None = None,
) -> DocumentBlock:
    return DocumentBlock(
        block_type=block_type,
        content=content,
        page_number_style=page_number_style,
        metadata=metadata or {},
    )


def render_timeless_wisdom(section: TimelessWisdomSection) -> List[DocumentBlock]:
    """
    HEADING("Timeless Wisdom")
    BLOCK_QUOTE(quote_text)
    FOOTNOTE(Turabian attribution)

    The FOOTNOTE block carries full attribution metadata for the PDF engine to render
    as a Turabian-style footnote at the bottom of the page (FR-63).
    """
    year = section.publication_year or "n.d."
    turabian = f"{section.author}, {section.source_title} ({year}), {section.page_or_url}."
    return [
        _block(BlockType.HEADING, "Timeless Wisdom"),
        _block(
            BlockType.BLOCK_QUOTE,
            section.quote_text,
            metadata={"footnote_id": "tw"},
        ),
        _block(
            BlockType.FOOTNOTE,
            turabian,
            metadata={
                "footnote_id": "tw",
                "author": section.author,
                "source_title": section.source_title,
                "publication_year": section.publication_year,
                "page_or_url": section.page_or_url,
            },
        ),
    ]


def render_scripture(section: ScriptureSection) -> List[DocumentBlock]:
    """
    HEADING("Scripture Reading")
    BODY_TEXT(reference with translation)
    BLOCK_QUOTE(scripture text)
    """
    return [
        _block(BlockType.HEADING, "Scripture Reading"),
        _block(BlockType.BODY_TEXT, f"{section.reference} ({section.translation})"),
        _block(BlockType.BLOCK_QUOTE, section.text),
    ]


def render_exposition(section: ExpositionSection) -> List[DocumentBlock]:
    """
    HEADING("Reflection")   — reader-facing label is "Reflection", not "Exposition" (PRD D016)
    BODY_TEXT(full exposition text)

    The Grounding Map is NOT included in the DocumentRepresentation; it is a UI
    artifact displayed in the Review UI alongside the exposition (FR-79a).
    """
    return [
        _block(BlockType.HEADING, "Reflection"),
        _block(BlockType.BODY_TEXT, section.text),
    ]


def render_be_still(section: BeStillSection) -> List[DocumentBlock]:
    """
    HEADING("Still Before God")
    PROMPT_LIST(prompts joined by newline — PDF engine splits on newline)
    """
    return [
        _block(BlockType.HEADING, "Still Before God"),
        _block(BlockType.PROMPT_LIST, "\n".join(section.prompts)),
    ]


def render_action_steps(section: ActionStepsSection) -> List[DocumentBlock]:
    """
    HEADING("Walk It Out")
    BODY_TEXT(connector phrase)
    ACTION_LIST(items joined by newline — PDF engine splits on newline)
    """
    return [
        _block(BlockType.HEADING, "Walk It Out"),
        _block(BlockType.BODY_TEXT, section.connector_phrase),
        _block(BlockType.ACTION_LIST, "\n".join(section.items)),
    ]


def render_prayer(section: PrayerSection) -> List[DocumentBlock]:
    """
    HEADING("Prayer")
    BODY_TEXT(prayer text)

    The Prayer Trace Map is NOT included in the DocumentRepresentation; it is a UI
    artifact displayed in the Review UI (FR-79a).
    """
    return [
        _block(BlockType.HEADING, "Prayer"),
        _block(BlockType.BODY_TEXT, section.text),
    ]


def render_sending_prompt(section: SendingPromptSection) -> List[DocumentBlock]:
    """
    DIVIDER (typographic rule — no section heading per FR-95)
    BODY_TEXT(sending prompt text)

    The sending prompt appears at the close of Day 6, separated from the prayer by
    a divider. It has no reader-facing section header.
    """
    return [
        _block(BlockType.DIVIDER, ""),
        _block(BlockType.BODY_TEXT, section.text),
    ]


def render_day7(section: Day7Section) -> List[DocumentBlock]:
    """
    HEADING("Before the Service")
    BODY_TEXT(before_service)
    DIVIDER
    HEADING("After the Service")
    HEADING("Track A — When the sermon connected with this week's theme")  [heading_level=2]
    PROMPT_LIST(after_service_track_a)
    HEADING("Track B — When the sermon went somewhere else")               [heading_level=2]
    PROMPT_LIST(after_service_track_b)

    Track A and Track B are given equal structural weight (FR-96, PRD D056).
    """
    return [
        _block(BlockType.HEADING, "Before the Service"),
        _block(BlockType.BODY_TEXT, section.before_service),
        _block(BlockType.DIVIDER, ""),
        _block(BlockType.HEADING, "After the Service"),
        _block(
            BlockType.HEADING,
            "Track A \u2014 When the sermon connected with this week\u2019s theme",
            metadata={"heading_level": 2},
        ),
        _block(BlockType.PROMPT_LIST, "\n".join(section.after_service_track_a)),
        _block(
            BlockType.HEADING,
            "Track B \u2014 When the sermon went somewhere else",
            metadata={"heading_level": 2},
        ),
        _block(BlockType.PROMPT_LIST, "\n".join(section.after_service_track_b)),
    ]
