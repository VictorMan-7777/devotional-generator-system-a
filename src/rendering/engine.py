"""DocumentRenderer: DevotionalBook → DocumentRepresentation.

Orchestrates front matter renderers and section renderers into a complete
DocumentRepresentation ready for Phase 003 PDF export.
"""

from datetime import datetime
from typing import List

from src.models.devotional import DevotionalBook, DailyDevotional, OutputMode
from src.models.document import BlockType, DocumentBlock, DocumentPage, DocumentRepresentation, PageNumberStyle
from src.rendering.front_matter import (
    render_copyright_page,
    render_introduction,
    render_offer_page,
    render_title_page,
    render_toc,
)
from src.rendering.sections import (
    render_action_steps,
    render_be_still,
    render_day7,
    render_exposition,
    render_prayer,
    render_scripture,
    render_sending_prompt,
    render_timeless_wisdom,
)

def _introduction_text(num_days: int) -> str:
    return (
        f"This devotional is structured for {num_days} days of personal reading, reflection, "
        "and prayer. Each day follows the same rhythm: a timeless quote, a scripture "
        "passage, a reflection, a moment of stillness, action steps, and a closing prayer. "
        "Begin on any day of the week. The order within each day is intentional — let each "
        "element do its work before moving to the next."
    )


def _title_page_subtitle(book: DevotionalBook) -> str:
    return f"{book.input.num_days}-Day Devotional"


def _title_page_tagline(book: DevotionalBook) -> str:
    topic = (book.input.topic or "").strip()
    if topic:
        return f"Scripture-shaped reflection through {topic}."
    return "Scripture-shaped reflection for attentive readers."


class DocumentRenderer:
    """Converts a DevotionalBook into a DocumentRepresentation."""

    def render(
        self,
        book: DevotionalBook,
        output_mode: OutputMode,
    ) -> DocumentRepresentation:
        """
        Render pipeline:
        1. Compute document-level flags (has_day7, title)
        2. Build front matter pages (title, copyright, introduction, optional TOC)
        3. Render each day into a content page
        4. Append Day 7 integration page when day.day7 is not None
        5. Append offer page
        6. Return DocumentRepresentation
        """
        has_day7 = any(day.day7 is not None for day in book.days)
        # TOC is opt-in for special cases; default devotional output should not
        # include it unless we explicitly wire a request through the pipeline.
        has_toc = False
        title = book.input.title or book.input.topic

        # --- Front matter ---
        front_matter: List[DocumentPage] = [
            render_title_page(
                title,
                subtitle=_title_page_subtitle(book),
                tagline=_title_page_tagline(book),
            ),
            render_copyright_page(datetime.now().year),
            render_introduction(has_day7=has_day7, introduction_text=_introduction_text(len(book.days))),
        ]
        if has_toc:
            front_matter.extend(render_toc(book.days))

        # --- Content pages ---
        content_pages: List[DocumentPage] = []
        endnote_blocks: List[DocumentBlock] = []
        footnote_index = 1

        for day in book.days:
            # Build all blocks for this day onto a single page.
            blocks = []
            week_number = ((day.day_number - 1) // 7) + 1
            blocks.append(
                DocumentBlock(
                    block_type=BlockType.SUBTITLE,
                    content=f"Week {week_number} · Day {day.day_number}",
                    page_number_style=PageNumberStyle.ARABIC,
                    metadata={"align": "center"},
                )
            )
            blocks.append(
                DocumentBlock(
                    block_type=BlockType.TITLE,
                    content=(day.day_focus or day.scripture.reference).strip(),
                    page_number_style=PageNumberStyle.ARABIC,
                    metadata={"align": "center"},
                )
            )
            blocks.append(
                DocumentBlock(
                    block_type=BlockType.DIVIDER,
                    content="",
                    page_number_style=PageNumberStyle.ARABIC,
                )
            )
            blocks.extend(render_timeless_wisdom(day.timeless_wisdom))
            blocks.extend(render_scripture(day.scripture))
            blocks.extend(render_exposition(day.exposition))
            blocks.extend(render_be_still(day.be_still))
            blocks.extend(render_action_steps(day.action_steps))
            blocks.extend(render_prayer(day.prayer))

            # Sending prompt: appended to Day 6's page, not a new page (FR-95).
            if day.sending_prompt is not None:
                blocks.extend(render_sending_prompt(day.sending_prompt))

            day_blocks: List[DocumentBlock] = []
            for block in blocks:
                if block.block_type == BlockType.FOOTNOTE:
                    endnote_blocks.append(
                        DocumentBlock(
                            block_type=BlockType.BODY_TEXT,
                            content=f"{footnote_index}. {block.content}",
                            page_number_style=PageNumberStyle.ARABIC,
                            metadata=block.metadata,
                        )
                    )
                    footnote_index += 1
                    continue
                day_blocks.append(block)

            content_pages.append(
                DocumentPage(
                    blocks=day_blocks,
                    starts_new_page=True,
                    page_number_style=PageNumberStyle.ARABIC,
                )
            )

            # Day 7 Sunday integration: a separate new page after the regular Day 7 page.
            if day.day7 is not None:
                content_pages.append(
                    DocumentPage(
                        blocks=render_day7(day.day7),
                        starts_new_page=True,
                        page_number_style=PageNumberStyle.ARABIC,
                    )
                )

        # --- End-of-volume footnotes (initial competition behavior) ---
        if endnote_blocks:
            content_pages.append(
                DocumentPage(
                    blocks=[DocumentBlock(block_type=BlockType.HEADING, content="Footnotes")] + endnote_blocks,
                    starts_new_page=True,
                    page_number_style=PageNumberStyle.ARABIC,
                )
            )

        # --- Offer page (final page of every export, FR-94) ---
        content_pages.append(render_offer_page())

        return DocumentRepresentation(
            title=title,
            subtitle=None,
            front_matter=front_matter,
            content_pages=content_pages,
            has_toc=has_toc,
            has_day7=has_day7,
        )
