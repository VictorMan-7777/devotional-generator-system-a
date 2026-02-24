"""DocumentRenderer: DevotionalBook → DocumentRepresentation.

Orchestrates front matter renderers and section renderers into a complete
DocumentRepresentation ready for Phase 003 PDF export.
"""

from datetime import datetime
from typing import List

from src.models.devotional import DevotionalBook, DailyDevotional, OutputMode
from src.models.document import DocumentPage, DocumentRepresentation, PageNumberStyle
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

_INTRODUCTION_TEXT = (
    "This devotional is structured for six days of personal reading, reflection, "
    "and prayer. Each day follows the same rhythm: a timeless quote, a scripture "
    "passage, a reflection, a moment of stillness, action steps, and a closing prayer. "
    "Begin on any day of the week. The order within each day is intentional — let each "
    "element do its work before moving to the next."
)


class DocumentRenderer:
    """Converts a DevotionalBook into a DocumentRepresentation."""

    def render(
        self,
        book: DevotionalBook,
        output_mode: OutputMode,
    ) -> DocumentRepresentation:
        """
        Render pipeline:
        1. Compute document-level flags (has_toc, has_day7, title)
        2. Build front matter pages (title, copyright, introduction, optional TOC)
        3. Render each day into a content page
        4. Append Day 7 integration page when day.day7 is not None
        5. Append offer page
        6. Return DocumentRepresentation
        """
        has_day7 = any(day.day7 is not None for day in book.days)
        has_toc = len(book.days) >= 12
        title = book.input.title or book.input.topic

        # --- Front matter ---
        front_matter: List[DocumentPage] = [
            render_title_page(title),
            render_copyright_page(datetime.now().year),
            render_introduction(has_day7=has_day7, introduction_text=_INTRODUCTION_TEXT),
        ]
        if has_toc:
            front_matter.extend(render_toc(book.days))

        # --- Content pages ---
        content_pages: List[DocumentPage] = []

        for day in book.days:
            # Build all blocks for this day onto a single page.
            blocks = []
            blocks.extend(render_timeless_wisdom(day.timeless_wisdom))
            blocks.extend(render_scripture(day.scripture))
            blocks.extend(render_exposition(day.exposition))
            blocks.extend(render_be_still(day.be_still))
            blocks.extend(render_action_steps(day.action_steps))
            blocks.extend(render_prayer(day.prayer))

            # Sending prompt: appended to Day 6's page, not a new page (FR-95).
            if day.sending_prompt is not None:
                blocks.extend(render_sending_prompt(day.sending_prompt))

            content_pages.append(
                DocumentPage(
                    blocks=blocks,
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
