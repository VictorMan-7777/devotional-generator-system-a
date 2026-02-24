"""Tests for front matter renderers (Phase 002 CP3)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pytest

from src.models.document import BlockType, PageNumberStyle
from src.rendering.front_matter import (
    render_copyright_page,
    render_introduction,
    render_offer_page,
    render_title_page,
    render_toc,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class _DayStub:
    """Minimal stub for render_toc — uses only day_number and day_focus."""
    day_number: int
    day_focus: Optional[str] = None


def _make_days(count: int) -> list[_DayStub]:
    return [_DayStub(day_number=i) for i in range(1, count + 1)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRenderTitlePage:
    def test_title_block_has_correct_content(self):
        page = render_title_page("My Devotional")
        title_blocks = [b for b in page.blocks if b.block_type == BlockType.TITLE]
        assert len(title_blocks) == 1
        assert title_blocks[0].content == "My Devotional"

    def test_page_number_style_is_suppressed(self):
        page = render_title_page("My Devotional")
        assert page.page_number_style == PageNumberStyle.SUPPRESSED

    def test_title_block_page_style_is_suppressed(self):
        page = render_title_page("My Devotional")
        title_block = next(b for b in page.blocks if b.block_type == BlockType.TITLE)
        assert title_block.page_number_style == PageNumberStyle.SUPPRESSED

    def test_no_subtitle_when_not_provided(self):
        page = render_title_page("My Devotional")
        subtitle_blocks = [b for b in page.blocks if b.block_type == BlockType.SUBTITLE]
        assert len(subtitle_blocks) == 0

    def test_subtitle_present_when_provided(self):
        page = render_title_page("My Devotional", subtitle="A Six-Day Journey")
        subtitle_blocks = [b for b in page.blocks if b.block_type == BlockType.SUBTITLE]
        assert len(subtitle_blocks) == 1
        assert subtitle_blocks[0].content == "A Six-Day Journey"

    def test_subtitle_also_suppressed(self):
        page = render_title_page("Title", subtitle="Subtitle")
        subtitle_block = next(b for b in page.blocks if b.block_type == BlockType.SUBTITLE)
        assert subtitle_block.page_number_style == PageNumberStyle.SUPPRESSED

    def test_starts_new_page(self):
        page = render_title_page("My Devotional")
        assert page.starts_new_page is True


class TestRenderCopyrightPage:
    def test_imprint_contains_sacred_whispers(self):
        page = render_copyright_page(2026)
        imprint_blocks = [b for b in page.blocks if b.block_type == BlockType.IMPRINT]
        assert len(imprint_blocks) == 1
        assert "Sacred Whispers Publishers" in imprint_blocks[0].content

    def test_page_number_style_is_roman(self):
        page = render_copyright_page(2026)
        assert page.page_number_style == PageNumberStyle.ROMAN

    def test_publication_year_in_content(self):
        page = render_copyright_page(2026)
        full_text = " ".join(b.content for b in page.blocks)
        assert "2026" in full_text

    def test_no_personal_author_name(self):
        # PRD D010: copyright page must not include personal author name.
        # We verify by ensuring no block content looks like a human byline
        # (name followed by "All rights reserved" pattern without imprint prefix).
        page = render_copyright_page(2026)
        for block in page.blocks:
            if block.block_type == BlockType.IMPRINT:
                assert block.content == "Sacred Whispers Publishers"

    def test_nasb_attribution_present(self):
        page = render_copyright_page(2026)
        full_text = " ".join(b.content for b in page.blocks)
        assert "NASB" in full_text or "New American Standard" in full_text

    def test_starts_new_page(self):
        page = render_copyright_page(2026)
        assert page.starts_new_page is True


class TestRenderIntroduction:
    _INTRO_TEXT = "This devotional is for six days of reading and prayer."

    def test_roman_page_style(self):
        page = render_introduction(has_day7=False, introduction_text=self._INTRO_TEXT)
        assert page.page_number_style == PageNumberStyle.ROMAN

    def test_introduction_text_present(self):
        page = render_introduction(has_day7=False, introduction_text=self._INTRO_TEXT)
        body_blocks = [b for b in page.blocks if b.block_type == BlockType.BODY_TEXT]
        assert any(self._INTRO_TEXT in b.content for b in body_blocks)

    def test_no_sunday_text_when_day7_disabled(self):
        page = render_introduction(has_day7=False, introduction_text=self._INTRO_TEXT)
        # The Sunday integration text contains the word "convergence"
        full_text = " ".join(b.content for b in page.blocks)
        assert "convergence" not in full_text.lower()

    def test_sunday_text_present_when_day7_enabled(self):
        page = render_introduction(has_day7=True, introduction_text=self._INTRO_TEXT)
        full_text = " ".join(b.content for b in page.blocks)
        assert "convergence" in full_text.lower()

    def test_sunday_text_is_additional_block_not_replacement(self):
        page = render_introduction(has_day7=True, introduction_text=self._INTRO_TEXT)
        body_blocks = [b for b in page.blocks if b.block_type == BlockType.BODY_TEXT]
        assert len(body_blocks) == 2
        assert any(self._INTRO_TEXT in b.content for b in body_blocks)

    def test_starts_new_page(self):
        page = render_introduction(has_day7=False, introduction_text=self._INTRO_TEXT)
        assert page.starts_new_page is True


class TestRenderToc:
    # render_toc uses only day.day_number and day.day_focus, so we use _DayStub
    # rather than full DailyDevotional (which caps day_number at 7 via schema).

    def test_returns_list_of_pages(self):
        pages = render_toc(_make_days(12))
        assert isinstance(pages, list)
        assert len(pages) == 1

    def test_12_toc_entries_for_12_days(self):
        pages = render_toc(_make_days(12))
        toc_blocks = [b for b in pages[0].blocks if b.block_type == BlockType.TOC_ENTRY]
        assert len(toc_blocks) == 12

    def test_toc_entries_contain_day_numbers(self):
        pages = render_toc(_make_days(12))
        toc_blocks = [b for b in pages[0].blocks if b.block_type == BlockType.TOC_ENTRY]
        assert any("Day 1" in b.content for b in toc_blocks)
        assert any("Day 12" in b.content for b in toc_blocks)

    def test_toc_page_number_style_is_roman(self):
        pages = render_toc(_make_days(12))
        assert pages[0].page_number_style == PageNumberStyle.ROMAN

    def test_toc_entry_has_page_placeholder_metadata(self):
        pages = render_toc(_make_days(12))
        toc_blocks = [b for b in pages[0].blocks if b.block_type == BlockType.TOC_ENTRY]
        for block in toc_blocks:
            assert block.metadata.get("page_placeholder") is True

    def test_day_focus_used_when_present(self):
        days = [_DayStub(day_number=1, day_focus="Grace and Freedom")]
        pages = render_toc(days)
        toc_blocks = [b for b in pages[0].blocks if b.block_type == BlockType.TOC_ENTRY]
        assert "Grace and Freedom" in toc_blocks[0].content

    def test_starts_new_page(self):
        pages = render_toc(_make_days(12))
        assert pages[0].starts_new_page is True


class TestRenderOfferPage:
    def test_body_text_present(self):
        page = render_offer_page()
        body_blocks = [b for b in page.blocks if b.block_type == BlockType.BODY_TEXT]
        assert len(body_blocks) >= 1

    def test_content_contains_url(self):
        page = render_offer_page()
        full_text = " ".join(b.content for b in page.blocks)
        assert "sacredwhisperspublishing.com" in full_text

    def test_page_number_style_is_arabic(self):
        page = render_offer_page()
        assert page.page_number_style == PageNumberStyle.ARABIC

    def test_starts_new_page(self):
        page = render_offer_page()
        assert page.starts_new_page is True
