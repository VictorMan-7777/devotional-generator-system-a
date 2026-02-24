"""Tests for DocumentRepresentation schema (Phase 002 CP1)."""

import json

import pytest

from src.models.document import (
    BlockType,
    DocumentBlock,
    DocumentPage,
    DocumentRepresentation,
    PageNumberStyle,
)


class TestBlockType:
    def test_heading_value(self):
        assert BlockType.HEADING == "heading"

    def test_body_text_value(self):
        assert BlockType.BODY_TEXT == "body_text"

    def test_block_quote_value(self):
        assert BlockType.BLOCK_QUOTE == "block_quote"

    def test_footnote_value(self):
        assert BlockType.FOOTNOTE == "footnote"

    def test_prompt_list_value(self):
        assert BlockType.PROMPT_LIST == "prompt_list"

    def test_action_list_value(self):
        assert BlockType.ACTION_LIST == "action_list"

    def test_divider_value(self):
        assert BlockType.DIVIDER == "divider"

    def test_page_break_value(self):
        assert BlockType.PAGE_BREAK == "page_break"

    def test_title_value(self):
        assert BlockType.TITLE == "title"

    def test_subtitle_value(self):
        assert BlockType.SUBTITLE == "subtitle"

    def test_imprint_value(self):
        assert BlockType.IMPRINT == "imprint"

    def test_toc_entry_value(self):
        assert BlockType.TOC_ENTRY == "toc_entry"


class TestPageNumberStyle:
    def test_roman_value(self):
        assert PageNumberStyle.ROMAN == "roman"

    def test_arabic_value(self):
        assert PageNumberStyle.ARABIC == "arabic"

    def test_suppressed_value(self):
        assert PageNumberStyle.SUPPRESSED == "suppressed"


class TestDocumentBlock:
    def test_minimal_instantiation(self):
        block = DocumentBlock(block_type=BlockType.HEADING, content="Hello")
        assert block.block_type == BlockType.HEADING
        assert block.content == "Hello"

    def test_metadata_defaults_to_empty_dict(self):
        block = DocumentBlock(block_type=BlockType.BODY_TEXT, content="text")
        assert block.metadata == {}

    def test_page_number_style_defaults_to_arabic(self):
        block = DocumentBlock(block_type=BlockType.BODY_TEXT, content="text")
        assert block.page_number_style == PageNumberStyle.ARABIC

    def test_metadata_accepts_arbitrary_keys(self):
        block = DocumentBlock(
            block_type=BlockType.FOOTNOTE,
            content="Author, Title (2020), p. 42",
            metadata={"footnote_id": "tw", "author": "Author", "publication_year": 2020},
        )
        assert block.metadata["footnote_id"] == "tw"
        assert block.metadata["publication_year"] == 2020

    def test_suppressed_page_style(self):
        block = DocumentBlock(
            block_type=BlockType.TITLE,
            content="My Book",
            page_number_style=PageNumberStyle.SUPPRESSED,
        )
        assert block.page_number_style == PageNumberStyle.SUPPRESSED


class TestDocumentPage:
    def test_empty_blocks_list(self):
        page = DocumentPage(blocks=[])
        assert page.blocks == []

    def test_starts_new_page_defaults_false(self):
        page = DocumentPage(blocks=[])
        assert page.starts_new_page is False

    def test_page_number_style_defaults_to_arabic(self):
        page = DocumentPage(blocks=[])
        assert page.page_number_style == PageNumberStyle.ARABIC

    def test_page_with_blocks(self):
        block = DocumentBlock(block_type=BlockType.HEADING, content="Section")
        page = DocumentPage(blocks=[block], starts_new_page=True)
        assert len(page.blocks) == 1
        assert page.starts_new_page is True

    def test_roman_page_style(self):
        page = DocumentPage(blocks=[], page_number_style=PageNumberStyle.ROMAN)
        assert page.page_number_style == PageNumberStyle.ROMAN


class TestDocumentRepresentation:
    def _minimal(self) -> DocumentRepresentation:
        return DocumentRepresentation(
            title="Test Book",
            front_matter=[],
            content_pages=[],
            has_toc=False,
            has_day7=False,
        )

    def test_minimal_instantiation(self):
        doc = self._minimal()
        assert doc.title == "Test Book"
        assert doc.has_toc is False
        assert doc.has_day7 is False

    def test_subtitle_defaults_none(self):
        doc = self._minimal()
        assert doc.subtitle is None

    def test_total_estimated_pages_defaults_none(self):
        doc = self._minimal()
        assert doc.total_estimated_pages is None

    def test_json_round_trip(self):
        doc = self._minimal()
        serialized = doc.model_dump_json()
        # Must be valid JSON
        parsed = json.loads(serialized)
        assert parsed["title"] == "Test Book"
        # Round-trip via model_validate_json
        restored = DocumentRepresentation.model_validate_json(serialized)
        assert restored.title == doc.title
        assert restored.has_toc == doc.has_toc
        assert restored.has_day7 == doc.has_day7

    def test_subtitle_none_round_trips(self):
        doc = DocumentRepresentation(
            title="Book",
            subtitle=None,
            front_matter=[],
            content_pages=[],
            has_toc=False,
            has_day7=False,
        )
        restored = DocumentRepresentation.model_validate_json(doc.model_dump_json())
        assert restored.subtitle is None

    def test_full_document_round_trips(self):
        block = DocumentBlock(
            block_type=BlockType.HEADING,
            content="Timeless Wisdom",
            metadata={"footnote_id": "tw"},
        )
        page = DocumentPage(
            blocks=[block],
            starts_new_page=True,
            page_number_style=PageNumberStyle.ARABIC,
        )
        fm_page = DocumentPage(
            blocks=[DocumentBlock(block_type=BlockType.TITLE, content="My Book")],
            page_number_style=PageNumberStyle.SUPPRESSED,
        )
        doc = DocumentRepresentation(
            title="My Book",
            subtitle="A Devotional",
            front_matter=[fm_page],
            content_pages=[page],
            has_toc=False,
            has_day7=True,
            total_estimated_pages=48,
        )
        restored = DocumentRepresentation.model_validate_json(doc.model_dump_json())
        assert restored.subtitle == "A Devotional"
        assert restored.has_day7 is True
        assert restored.total_estimated_pages == 48
        assert len(restored.front_matter) == 1
        assert len(restored.content_pages) == 1
        assert restored.content_pages[0].blocks[0].block_type == BlockType.HEADING
        assert restored.content_pages[0].blocks[0].metadata["footnote_id"] == "tw"
