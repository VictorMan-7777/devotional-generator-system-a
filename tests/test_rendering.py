"""End-to-end rendering tests (Phase 002 CP4).

Tests the DocumentRenderer.render() pipeline using SAMPLE_BOOK and minimal
inline fixtures. SAMPLE_BOOK has 7 DailyDevotional entries (days 1–7):
  - Day 6 has sending_prompt
  - Day 7 has day7 section

Expected content_pages for SAMPLE_BOOK (publish-ready):
  9 = 7 day pages + 1 Day 7 integration page + 1 offer page
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pytest

from src.models.devotional import (
    ActionStepsSection,
    BeStillSection,
    DailyDevotional,
    DevotionalBook,
    DevotionalInput,
    ExpositionSection,
    OutputMode,
    PrayerSection,
    ScriptureSection,
    TimelessWisdomSection,
)
from src.models.document import BlockType, PageNumberStyle
from src.rendering.engine import DocumentRenderer
from tests.fixtures.sample_devotional import SAMPLE_BOOK

_RENDERER = DocumentRenderer()
_NOW = datetime(2026, 2, 24, 12, 0, 0)


# ---------------------------------------------------------------------------
# Helper: minimal day factory for inline fixtures
# ---------------------------------------------------------------------------

def _make_day(day_number: int = 1) -> DailyDevotional:
    return DailyDevotional(
        day_number=day_number,
        timeless_wisdom=TimelessWisdomSection(
            quote_text="A fixture quote.",
            author="Fixture Author",
            source_title="Fixture Source",
            publication_year=2000,
            page_or_url="p. 1",
            public_domain=False,
            verification_status="catalog_verified",
        ),
        scripture=ScriptureSection(
            reference="John 1:1",
            text="In the beginning was the Word.",
            translation="NASB",
            retrieval_source="bolls_life",
            verification_status="bolls_life_verified",
        ),
        exposition=ExpositionSection(
            text="Reflection text. " * 40,
            word_count=520,
            grounding_map_id="gm-inline",
        ),
        be_still=BeStillSection(prompts=["Pause.", "Listen.", "Receive."]),
        action_steps=ActionStepsSection(
            items=["Take one step."], connector_phrase="Today:"
        ),
        prayer=PrayerSection(
            text="Lord, lead me. " * 10,
            word_count=130,
            prayer_trace_map_id="ptm-inline",
        ),
        created_at=_NOW,
        last_modified=_NOW,
    )


def _make_book(num_days: int) -> DevotionalBook:
    """Build a DevotionalBook with `num_days` standard days (no day7, no sending_prompt).
    day_number cycles through 1–7 to satisfy schema constraint (le=7).
    """
    days = [_make_day((i % 7) + 1) for i in range(num_days)]
    return DevotionalBook(
        id="inline-fixture",
        input=DevotionalInput(
            topic="Inline Fixture",
            num_days=min(num_days, 7),
        ),
        days=days,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPageCount:
    def test_6_day_book_page_count(self):
        # 6 days, no day7, no sending_prompt → 6 day pages + 1 offer page = 7
        book = _make_book(6)
        doc = _RENDERER.render(book, OutputMode.PUBLISH_READY)
        assert len(doc.content_pages) == 7

    def test_sample_book_content_pages(self):
        # SAMPLE_BOOK: 7 day pages + 1 Day 7 integration page + 1 offer page = 9
        doc = _RENDERER.render(SAMPLE_BOOK, OutputMode.PUBLISH_READY)
        assert len(doc.content_pages) == 9


class TestTocRendering:
    def test_toc_not_rendered_under_12_days(self):
        doc = _RENDERER.render(SAMPLE_BOOK, OutputMode.PUBLISH_READY)
        assert doc.has_toc is False
        # No TOC_ENTRY blocks in any front_matter page
        for page in doc.front_matter:
            for block in page.blocks:
                assert block.block_type != BlockType.TOC_ENTRY

    def test_toc_rendered_for_12_plus_days(self):
        # 12 days (day_numbers cycle 1–7 per schema constraint)
        book = _make_book(12)
        doc = _RENDERER.render(book, OutputMode.PUBLISH_READY)
        assert doc.has_toc is True
        toc_blocks = [
            block
            for page in doc.front_matter
            for block in page.blocks
            if block.block_type == BlockType.TOC_ENTRY
        ]
        assert len(toc_blocks) == 12


class TestDay7Rendering:
    def test_day7_not_rendered_when_disabled(self):
        # 6 days, no day7 field set
        book = _make_book(6)
        doc = _RENDERER.render(book, OutputMode.PUBLISH_READY)
        assert doc.has_day7 is False
        # 7 content pages: 6 day pages + offer
        assert len(doc.content_pages) == 7

    def test_day7_page_has_before_service_heading(self):
        doc = _RENDERER.render(SAMPLE_BOOK, OutputMode.PUBLISH_READY)
        # Day 7 integration page is content_pages[7] (0-indexed):
        # pages 0–6 = day 1–7 regular pages; page 7 = Day 7 integration; page 8 = offer
        day7_integration_page = doc.content_pages[7]
        headings = [
            b.content for b in day7_integration_page.blocks
            if b.block_type == BlockType.HEADING
        ]
        assert "Before the Service" in headings

    def test_day7_page_has_after_service_heading(self):
        doc = _RENDERER.render(SAMPLE_BOOK, OutputMode.PUBLISH_READY)
        day7_integration_page = doc.content_pages[7]
        headings = [
            b.content for b in day7_integration_page.blocks
            if b.block_type == BlockType.HEADING
        ]
        assert "After the Service" in headings

    def test_has_day7_flag_true_for_sample_book(self):
        doc = _RENDERER.render(SAMPLE_BOOK, OutputMode.PUBLISH_READY)
        assert doc.has_day7 is True


class TestSendingPrompt:
    def test_sending_prompt_on_day6_page_not_new_page(self):
        doc = _RENDERER.render(SAMPLE_BOOK, OutputMode.PUBLISH_READY)
        # Day 6 is content_pages[5] (0-indexed days 0–6 = pages 0–6)
        day6_page = doc.content_pages[5]
        divider_blocks = [b for b in day6_page.blocks if b.block_type == BlockType.DIVIDER]
        # There should be a DIVIDER (from sending_prompt renderer) within Day 6's page
        assert len(divider_blocks) >= 1

    def test_sending_prompt_has_no_heading(self):
        # render_sending_prompt must produce no HEADING block (FR-95)
        from src.rendering.sections import render_sending_prompt
        from src.models.devotional import SendingPromptSection
        section = SendingPromptSection(
            text="Carry this into Sunday.",
            word_count=5,
        )
        blocks = render_sending_prompt(section)
        heading_blocks = [b for b in blocks if b.block_type == BlockType.HEADING]
        assert len(heading_blocks) == 0


class TestSectionHeadings:
    def _day1_blocks(self):
        doc = _RENDERER.render(SAMPLE_BOOK, OutputMode.PUBLISH_READY)
        return doc.content_pages[0].blocks

    def test_timeless_wisdom_has_footnote(self):
        blocks = self._day1_blocks()
        footnote_blocks = [b for b in blocks if b.block_type == BlockType.FOOTNOTE]
        assert len(footnote_blocks) >= 1

    def test_exposition_heading_is_reflection(self):
        blocks = self._day1_blocks()
        headings = [b.content for b in blocks if b.block_type == BlockType.HEADING]
        assert "Reflection" in headings
        assert "Exposition" not in headings

    def test_be_still_heading(self):
        blocks = self._day1_blocks()
        headings = [b.content for b in blocks if b.block_type == BlockType.HEADING]
        assert "Still Before God" in headings

    def test_action_steps_heading(self):
        blocks = self._day1_blocks()
        headings = [b.content for b in blocks if b.block_type == BlockType.HEADING]
        assert "Walk It Out" in headings


class TestOfferPage:
    def test_offer_page_is_final(self):
        doc = _RENDERER.render(SAMPLE_BOOK, OutputMode.PUBLISH_READY)
        last_page = doc.content_pages[-1]
        full_text = " ".join(b.content for b in last_page.blocks)
        assert "sacredwhisperspublishing.com" in full_text

    def test_offer_page_always_present(self):
        # Even for a 1-day book, offer page should be the final page
        book = _make_book(1)
        doc = _RENDERER.render(book, OutputMode.PUBLISH_READY)
        last_page = doc.content_pages[-1]
        full_text = " ".join(b.content for b in last_page.blocks)
        assert "sacredwhisperspublishing.com" in full_text


class TestPageNumberStyles:
    def test_front_matter_page_styles(self):
        doc = _RENDERER.render(SAMPLE_BOOK, OutputMode.PUBLISH_READY)
        allowed = {PageNumberStyle.ROMAN, PageNumberStyle.SUPPRESSED}
        for i, page in enumerate(doc.front_matter):
            assert page.page_number_style in allowed, (
                f"Front matter page {i} has unexpected style: {page.page_number_style}"
            )

    def test_content_pages_are_arabic(self):
        doc = _RENDERER.render(SAMPLE_BOOK, OutputMode.PUBLISH_READY)
        for i, page in enumerate(doc.content_pages):
            assert page.page_number_style == PageNumberStyle.ARABIC, (
                f"Content page {i} has unexpected style: {page.page_number_style}"
            )


class TestJsonSerialization:
    def test_document_is_json_serializable(self):
        doc = _RENDERER.render(SAMPLE_BOOK, OutputMode.PUBLISH_READY)
        serialized = doc.model_dump_json()
        assert isinstance(serialized, str)
        # Must be valid JSON
        parsed = json.loads(serialized)
        assert parsed["title"] == SAMPLE_BOOK.input.title
        assert "front_matter" in parsed
        assert "content_pages" in parsed
