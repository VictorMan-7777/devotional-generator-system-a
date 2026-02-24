"""Tests for section renderers (Phase 002 CP2)."""

from datetime import datetime

import pytest

from src.models.devotional import (
    ActionStepsSection,
    BeStillSection,
    Day7Section,
    ExpositionSection,
    PrayerSection,
    ScriptureSection,
    SectionApprovalStatus,
    SendingPromptSection,
    TimelessWisdomSection,
)
from src.models.document import BlockType, DocumentBlock
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _timeless_wisdom(**kwargs) -> TimelessWisdomSection:
    defaults = dict(
        quote_text="Be still and know that I am God.",
        author="C.S. Lewis",
        source_title="Mere Christianity",
        publication_year=1952,
        page_or_url="p. 42",
        public_domain=False,
        verification_status="catalog_verified",
    )
    defaults.update(kwargs)
    return TimelessWisdomSection(**defaults)


def _scripture(**kwargs) -> ScriptureSection:
    defaults = dict(
        reference="Romans 8:15",
        text="For you did not receive a spirit that makes you a slave again to fear.",
        translation="NASB",
        retrieval_source="bolls_life",
        verification_status="bolls_life_verified",
    )
    defaults.update(kwargs)
    return ScriptureSection(**defaults)


def _exposition(**kwargs) -> ExpositionSection:
    defaults = dict(
        text="This is the full exposition text." * 30,  # enough words
        word_count=540,
        grounding_map_id="gm-fixture-001",
    )
    defaults.update(kwargs)
    return ExpositionSection(**defaults)


def _be_still(**kwargs) -> BeStillSection:
    defaults = dict(prompts=["Sit quietly for two minutes.", "What word arose?", "Release it to God."])
    defaults.update(kwargs)
    return BeStillSection(**defaults)


def _action_steps(**kwargs) -> ActionStepsSection:
    defaults = dict(
        items=["Call a friend.", "Write one sentence."],
        connector_phrase="As you go today:",
    )
    defaults.update(kwargs)
    return ActionStepsSection(**defaults)


def _prayer(**kwargs) -> PrayerSection:
    defaults = dict(
        text="Father, thank you for your grace. " * 6,
        word_count=150,
        prayer_trace_map_id="ptm-fixture-001",
    )
    defaults.update(kwargs)
    return PrayerSection(**defaults)


def _sending_prompt(**kwargs) -> SendingPromptSection:
    defaults = dict(
        text="Carry this truth into Sunday: you are held.",
        word_count=9,
    )
    defaults.update(kwargs)
    return SendingPromptSection(**defaults)


def _day7(**kwargs) -> Day7Section:
    defaults = dict(
        before_service="Before you leave, hold this week's question in mind.",
        after_service_track_a=[
            "How did the sermon meet this week's theme?",
            "What image or phrase stayed with you?",
        ],
        after_service_track_b=[
            "Where did the sermon take you?",
            "Can you hold both threads?",
        ],
        after_service_word_count=140,
    )
    defaults.update(kwargs)
    return Day7Section(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRenderTimelessWisdom:
    def test_first_block_is_heading(self):
        blocks = render_timeless_wisdom(_timeless_wisdom())
        assert blocks[0].block_type == BlockType.HEADING
        assert blocks[0].content == "Timeless Wisdom"

    def test_block_quote_present(self):
        section = _timeless_wisdom()
        blocks = render_timeless_wisdom(section)
        quote_blocks = [b for b in blocks if b.block_type == BlockType.BLOCK_QUOTE]
        assert len(quote_blocks) == 1
        assert quote_blocks[0].content == section.quote_text

    def test_footnote_present(self):
        blocks = render_timeless_wisdom(_timeless_wisdom())
        footnote_blocks = [b for b in blocks if b.block_type == BlockType.FOOTNOTE]
        assert len(footnote_blocks) == 1

    def test_footnote_metadata_has_author(self):
        section = _timeless_wisdom()
        blocks = render_timeless_wisdom(section)
        footnote = next(b for b in blocks if b.block_type == BlockType.FOOTNOTE)
        assert footnote.metadata["author"] == "C.S. Lewis"

    def test_footnote_metadata_has_source_title(self):
        section = _timeless_wisdom()
        blocks = render_timeless_wisdom(section)
        footnote = next(b for b in blocks if b.block_type == BlockType.FOOTNOTE)
        assert footnote.metadata["source_title"] == "Mere Christianity"

    def test_footnote_content_contains_author(self):
        section = _timeless_wisdom()
        blocks = render_timeless_wisdom(section)
        footnote = next(b for b in blocks if b.block_type == BlockType.FOOTNOTE)
        assert "C.S. Lewis" in footnote.content

    def test_footnote_uses_nd_when_no_year(self):
        section = _timeless_wisdom(publication_year=None)
        blocks = render_timeless_wisdom(section)
        footnote = next(b for b in blocks if b.block_type == BlockType.FOOTNOTE)
        assert "n.d." in footnote.content

    def test_block_quote_has_footnote_id_metadata(self):
        blocks = render_timeless_wisdom(_timeless_wisdom())
        quote = next(b for b in blocks if b.block_type == BlockType.BLOCK_QUOTE)
        assert quote.metadata.get("footnote_id") == "tw"

    def test_returns_three_blocks(self):
        blocks = render_timeless_wisdom(_timeless_wisdom())
        assert len(blocks) == 3


class TestRenderScripture:
    def test_first_block_is_heading(self):
        blocks = render_scripture(_scripture())
        assert blocks[0].block_type == BlockType.HEADING
        assert blocks[0].content == "Scripture Reading"

    def test_body_text_contains_reference(self):
        section = _scripture()
        blocks = render_scripture(section)
        body_blocks = [b for b in blocks if b.block_type == BlockType.BODY_TEXT]
        assert any("Romans 8:15" in b.content for b in body_blocks)

    def test_body_text_contains_translation(self):
        section = _scripture()
        blocks = render_scripture(section)
        body_blocks = [b for b in blocks if b.block_type == BlockType.BODY_TEXT]
        assert any("NASB" in b.content for b in body_blocks)

    def test_block_quote_is_scripture_text(self):
        section = _scripture()
        blocks = render_scripture(section)
        quote_blocks = [b for b in blocks if b.block_type == BlockType.BLOCK_QUOTE]
        assert len(quote_blocks) == 1
        assert quote_blocks[0].content == section.text

    def test_returns_three_blocks(self):
        blocks = render_scripture(_scripture())
        assert len(blocks) == 3


class TestRenderExposition:
    def test_heading_is_reflection_not_exposition(self):
        blocks = render_exposition(_exposition())
        heading_blocks = [b for b in blocks if b.block_type == BlockType.HEADING]
        assert len(heading_blocks) == 1
        assert heading_blocks[0].content == "Reflection"
        assert "Exposition" not in heading_blocks[0].content

    def test_body_text_is_section_text(self):
        section = _exposition()
        blocks = render_exposition(section)
        body_blocks = [b for b in blocks if b.block_type == BlockType.BODY_TEXT]
        assert len(body_blocks) == 1
        assert body_blocks[0].content == section.text

    def test_no_grounding_map_content(self):
        blocks = render_exposition(_exposition())
        # Grounding map ID must not appear in any block content
        for block in blocks:
            assert "gm-fixture-001" not in block.content

    def test_returns_two_blocks(self):
        blocks = render_exposition(_exposition())
        assert len(blocks) == 2


class TestRenderBeStill:
    def test_heading_is_still_before_god(self):
        blocks = render_be_still(_be_still())
        heading_blocks = [b for b in blocks if b.block_type == BlockType.HEADING]
        assert len(heading_blocks) == 1
        assert heading_blocks[0].content == "Still Before God"

    def test_prompt_list_present(self):
        blocks = render_be_still(_be_still())
        prompt_blocks = [b for b in blocks if b.block_type == BlockType.PROMPT_LIST]
        assert len(prompt_blocks) == 1

    def test_prompt_list_contains_all_prompts(self):
        section = _be_still()
        blocks = render_be_still(section)
        prompt_block = next(b for b in blocks if b.block_type == BlockType.PROMPT_LIST)
        for prompt in section.prompts:
            assert prompt in prompt_block.content

    def test_returns_two_blocks(self):
        blocks = render_be_still(_be_still())
        assert len(blocks) == 2


class TestRenderActionSteps:
    def test_heading_is_walk_it_out(self):
        blocks = render_action_steps(_action_steps())
        heading_blocks = [b for b in blocks if b.block_type == BlockType.HEADING]
        assert len(heading_blocks) == 1
        assert heading_blocks[0].content == "Walk It Out"

    def test_body_text_is_connector_phrase(self):
        section = _action_steps()
        blocks = render_action_steps(section)
        body_blocks = [b for b in blocks if b.block_type == BlockType.BODY_TEXT]
        assert len(body_blocks) == 1
        assert body_blocks[0].content == section.connector_phrase

    def test_action_list_present(self):
        blocks = render_action_steps(_action_steps())
        action_blocks = [b for b in blocks if b.block_type == BlockType.ACTION_LIST]
        assert len(action_blocks) == 1

    def test_action_list_contains_items(self):
        section = _action_steps()
        blocks = render_action_steps(section)
        action_block = next(b for b in blocks if b.block_type == BlockType.ACTION_LIST)
        for item in section.items:
            assert item in action_block.content

    def test_returns_three_blocks(self):
        blocks = render_action_steps(_action_steps())
        assert len(blocks) == 3


class TestRenderPrayer:
    def test_heading_is_prayer(self):
        blocks = render_prayer(_prayer())
        heading_blocks = [b for b in blocks if b.block_type == BlockType.HEADING]
        assert len(heading_blocks) == 1
        assert heading_blocks[0].content == "Prayer"

    def test_body_text_is_prayer_text(self):
        section = _prayer()
        blocks = render_prayer(section)
        body_blocks = [b for b in blocks if b.block_type == BlockType.BODY_TEXT]
        assert len(body_blocks) == 1
        assert body_blocks[0].content == section.text

    def test_returns_two_blocks(self):
        blocks = render_prayer(_prayer())
        assert len(blocks) == 2


class TestRenderSendingPrompt:
    def test_no_heading_block(self):
        blocks = render_sending_prompt(_sending_prompt())
        heading_blocks = [b for b in blocks if b.block_type == BlockType.HEADING]
        assert len(heading_blocks) == 0

    def test_first_block_is_divider(self):
        blocks = render_sending_prompt(_sending_prompt())
        assert blocks[0].block_type == BlockType.DIVIDER

    def test_second_block_is_body_text(self):
        section = _sending_prompt()
        blocks = render_sending_prompt(section)
        assert blocks[1].block_type == BlockType.BODY_TEXT
        assert blocks[1].content == section.text

    def test_returns_two_blocks(self):
        blocks = render_sending_prompt(_sending_prompt())
        assert len(blocks) == 2


class TestRenderDay7:
    def test_before_the_service_heading_present(self):
        blocks = render_day7(_day7())
        headings = [b.content for b in blocks if b.block_type == BlockType.HEADING]
        assert "Before the Service" in headings

    def test_after_the_service_heading_present(self):
        blocks = render_day7(_day7())
        headings = [b.content for b in blocks if b.block_type == BlockType.HEADING]
        assert "After the Service" in headings

    def test_track_a_heading_present(self):
        blocks = render_day7(_day7())
        headings = [b.content for b in blocks if b.block_type == BlockType.HEADING]
        assert any("Track A" in h for h in headings)

    def test_track_b_heading_present(self):
        blocks = render_day7(_day7())
        headings = [b.content for b in blocks if b.block_type == BlockType.HEADING]
        assert any("Track B" in h for h in headings)

    def test_two_prompt_list_blocks(self):
        blocks = render_day7(_day7())
        prompt_blocks = [b for b in blocks if b.block_type == BlockType.PROMPT_LIST]
        assert len(prompt_blocks) == 2

    def test_track_a_prompts_in_first_prompt_list(self):
        section = _day7()
        blocks = render_day7(section)
        prompt_blocks = [b for b in blocks if b.block_type == BlockType.PROMPT_LIST]
        for prompt in section.after_service_track_a:
            assert prompt in prompt_blocks[0].content

    def test_track_b_prompts_in_second_prompt_list(self):
        section = _day7()
        blocks = render_day7(section)
        prompt_blocks = [b for b in blocks if b.block_type == BlockType.PROMPT_LIST]
        for prompt in section.after_service_track_b:
            assert prompt in prompt_blocks[1].content

    def test_before_service_body_text_present(self):
        section = _day7()
        blocks = render_day7(section)
        body_blocks = [b for b in blocks if b.block_type == BlockType.BODY_TEXT]
        assert any(section.before_service in b.content for b in body_blocks)

    def test_track_headings_have_heading_level_2_metadata(self):
        blocks = render_day7(_day7())
        track_headings = [
            b for b in blocks
            if b.block_type == BlockType.HEADING and "Track" in b.content
        ]
        assert len(track_headings) == 2
        for h in track_headings:
            assert h.metadata.get("heading_level") == 2
