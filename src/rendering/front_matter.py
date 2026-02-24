"""Front matter renderers: title page, copyright, introduction, TOC, offer page.

Template files are loaded from the project root `templates/` directory, resolved
relative to this file's location (src/rendering/ → three levels up to project root).
"""

from pathlib import Path
from typing import List, Optional

from src.models.devotional import DailyDevotional
from src.models.document import BlockType, DocumentBlock, DocumentPage, PageNumberStyle

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


def _read_template(filename: str) -> str:
    """Read a static template file from the templates/ directory."""
    path = _TEMPLATES_DIR / filename
    return path.read_text(encoding="utf-8").strip()


def _block(
    block_type: BlockType,
    content: str,
    *,
    page_number_style: PageNumberStyle = PageNumberStyle.ROMAN,
    metadata: dict | None = None,
) -> DocumentBlock:
    return DocumentBlock(
        block_type=block_type,
        content=content,
        page_number_style=page_number_style,
        metadata=metadata or {},
    )


def render_title_page(title: str, subtitle: Optional[str] = None) -> DocumentPage:
    """
    Title page: TITLE block, optional SUBTITLE block.
    Page number style: SUPPRESSED (title page carries no number).
    """
    blocks: List[DocumentBlock] = [
        _block(BlockType.TITLE, title, page_number_style=PageNumberStyle.SUPPRESSED),
    ]
    if subtitle is not None:
        blocks.append(
            _block(BlockType.SUBTITLE, subtitle, page_number_style=PageNumberStyle.SUPPRESSED)
        )
    return DocumentPage(
        blocks=blocks,
        starts_new_page=True,
        page_number_style=PageNumberStyle.SUPPRESSED,
    )


def render_copyright_page(publication_year: int) -> DocumentPage:
    """
    Copyright page: Sacred Whispers Publishers imprint + copyright notice.
    Page number style: ROMAN.
    No personal author name (PRD D010).
    """
    copyright_text = (
        f"Copyright \u00a9 {publication_year} Sacred Whispers Publishers\n\n"
        "All rights reserved. No part of this publication may be reproduced, "
        "distributed, or transmitted in any form or by any means without prior "
        "written permission from the publisher.\n\n"
        "Scripture quotations marked NASB are taken from the New American Standard "
        "Bible\u00ae, Copyright \u00a9 1960, 1971, 1977, 1995, 2020 by The Lockman "
        "Foundation. Used by permission. All rights reserved. www.lockman.org"
    )
    blocks: List[DocumentBlock] = [
        _block(BlockType.IMPRINT, "Sacred Whispers Publishers"),
        _block(BlockType.BODY_TEXT, copyright_text),
    ]
    return DocumentPage(
        blocks=blocks,
        starts_new_page=True,
        page_number_style=PageNumberStyle.ROMAN,
    )


def render_introduction(has_day7: bool, introduction_text: str) -> DocumentPage:
    """
    Introduction page: general introduction text, plus Sunday Worship Integration
    section appended when Day 7 is enabled (FR-97).
    Page number style: ROMAN.
    """
    blocks: List[DocumentBlock] = [
        _block(BlockType.BODY_TEXT, introduction_text),
    ]
    if has_day7:
        sunday_text = _read_template("introduction_sunday.md")
        blocks.append(_block(BlockType.BODY_TEXT, sunday_text))
    return DocumentPage(
        blocks=blocks,
        starts_new_page=True,
        page_number_style=PageNumberStyle.ROMAN,
    )


def render_toc(days: List[DailyDevotional]) -> List[DocumentPage]:
    """
    Table of contents page — only rendered when len(days) >= 12 (FR-89).
    Caller is responsible for the 12-day gate.

    TOC_ENTRY blocks carry page_placeholder=True in metadata; the PDF engine
    replaces placeholders with actual page numbers after layout.
    """
    blocks: List[DocumentBlock] = []
    for day in days:
        label = day.day_focus or f"Day {day.day_number}"
        entry = f"Day {day.day_number}: {label}"
        blocks.append(
            _block(
                BlockType.TOC_ENTRY,
                entry,
                metadata={"page_placeholder": True, "day_number": day.day_number},
            )
        )
    return [
        DocumentPage(
            blocks=blocks,
            starts_new_page=True,
            page_number_style=PageNumberStyle.ROMAN,
        )
    ]


def render_offer_page() -> DocumentPage:
    """
    Offer page — final page of every publish-ready export (FR-94).
    Content from templates/offer_page.md.
    Page number style: ARABIC (offer page is content, not front matter).
    """
    offer_text = _read_template("offer_page.md")
    return DocumentPage(
        blocks=[
            DocumentBlock(
                block_type=BlockType.BODY_TEXT,
                content=offer_text,
                page_number_style=PageNumberStyle.ARABIC,
            )
        ],
        starts_new_page=True,
        page_number_style=PageNumberStyle.ARABIC,
    )
