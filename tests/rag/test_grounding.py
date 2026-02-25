"""Unit tests for src/rag/grounding.py — GroundingMapBuilder.

Tests cover:
  - Valid build: 4 paragraphs with excerpts → GroundingMap passes Pydantic validator
  - Structural: exactly 4 entries, correct paragraph_number and names
  - Entry content: sources_retrieved and excerpts_used populated correctly
  - exposition_id threaded through correctly
  - Default paragraph names (declaration/context/theological/bridge)
  - Custom paragraph_names override
  - Error path: missing paragraph raises ValueError
  - Error path: empty excerpt list raises ValueError
"""
from __future__ import annotations

import pytest

from src.interfaces.rag import RetrievedExcerpt
from src.models.artifacts import GroundingMap
from src.rag.grounding import GroundingMapBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _excerpt(text: str, source: str = "Matthew Henry's Commentary") -> RetrievedExcerpt:
    return RetrievedExcerpt(
        text=text,
        source_title=source,
        author="Matthew Henry",
        source_type="commentary",
    )


def _four_paragraph_excerpts() -> dict:
    return {
        1: [_excerpt("Paragraph one text about declaration of truth.")],
        2: [_excerpt("Paragraph two text about contextual background."), _excerpt("Second context excerpt.")],
        3: [_excerpt("Paragraph three text about theological doctrine.")],
        4: [_excerpt("Paragraph four text about practical bridge.")],
    }


# ---------------------------------------------------------------------------
# Valid build
# ---------------------------------------------------------------------------


class TestValidBuild:
    def test_returns_grounding_map(self):
        gm = GroundingMapBuilder().build("expo-001", _four_paragraph_excerpts())
        assert isinstance(gm, GroundingMap)

    def test_pydantic_validator_passes(self):
        """GroundingMap field_validator must not raise — confirms structural correctness."""
        gm = GroundingMapBuilder().build("expo-001", _four_paragraph_excerpts())
        # Pydantic revalidates on construction; reaching here means no ValidationError.
        assert gm is not None

    def test_exposition_id_threaded(self):
        gm = GroundingMapBuilder().build("expo-42", _four_paragraph_excerpts())
        assert gm.exposition_id == "expo-42"

    def test_id_is_non_empty_string(self):
        gm = GroundingMapBuilder().build("expo-001", _four_paragraph_excerpts())
        assert isinstance(gm.id, str)
        assert gm.id != ""


# ---------------------------------------------------------------------------
# Structural correctness
# ---------------------------------------------------------------------------


class TestStructure:
    def test_exactly_four_entries(self):
        gm = GroundingMapBuilder().build("expo-001", _four_paragraph_excerpts())
        assert len(gm.entries) == 4

    def test_paragraph_numbers_are_1_to_4(self):
        gm = GroundingMapBuilder().build("expo-001", _four_paragraph_excerpts())
        assert [e.paragraph_number for e in gm.entries] == [1, 2, 3, 4]

    def test_default_paragraph_names(self):
        gm = GroundingMapBuilder().build("expo-001", _four_paragraph_excerpts())
        names = [e.paragraph_name for e in gm.entries]
        assert names == ["declaration", "context", "theological", "bridge"]

    def test_custom_paragraph_names_override(self):
        gm = GroundingMapBuilder().build(
            "expo-001",
            _four_paragraph_excerpts(),
            paragraph_names={2: "historical", 3: "doctrinal"},
        )
        names = [e.paragraph_name for e in gm.entries]
        assert names[0] == "declaration"   # default
        assert names[1] == "historical"   # overridden
        assert names[2] == "doctrinal"    # overridden
        assert names[3] == "bridge"       # default


# ---------------------------------------------------------------------------
# Entry content
# ---------------------------------------------------------------------------


class TestEntryContent:
    def test_sources_retrieved_non_empty(self):
        gm = GroundingMapBuilder().build("expo-001", _four_paragraph_excerpts())
        for entry in gm.entries:
            assert len(entry.sources_retrieved) > 0

    def test_excerpts_used_non_empty(self):
        gm = GroundingMapBuilder().build("expo-001", _four_paragraph_excerpts())
        for entry in gm.entries:
            assert len(entry.excerpts_used) > 0

    def test_excerpts_used_truncated_to_80_chars(self):
        long_text = "A" * 200
        excerpts = {
            1: [_excerpt(long_text)],
            2: [_excerpt(long_text)],
            3: [_excerpt(long_text)],
            4: [_excerpt(long_text)],
        }
        gm = GroundingMapBuilder().build("expo-001", excerpts)
        for entry in gm.entries:
            for used in entry.excerpts_used:
                assert len(used) <= 80

    def test_sources_retrieved_deduplicated(self):
        """Two excerpts from the same source → only one source_title entry."""
        excerpts = {
            1: [_excerpt("Excerpt A", source="Henry"), _excerpt("Excerpt B", source="Henry")],
            2: [_excerpt("Excerpt C")],
            3: [_excerpt("Excerpt D")],
            4: [_excerpt("Excerpt E")],
        }
        gm = GroundingMapBuilder().build("expo-001", excerpts)
        entry_1 = gm.entries[0]
        assert entry_1.sources_retrieved == ["Henry"]

    def test_how_retrieval_informed_paragraph_populated(self):
        gm = GroundingMapBuilder().build("expo-001", _four_paragraph_excerpts())
        for entry in gm.entries:
            assert entry.how_retrieval_informed_paragraph.strip()


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    def test_missing_paragraph_raises_value_error(self):
        incomplete = {
            1: [_excerpt("Para 1")],
            2: [_excerpt("Para 2")],
            # paragraph 3 missing
            4: [_excerpt("Para 4")],
        }
        with pytest.raises(ValueError, match="paragraph 3 missing"):
            GroundingMapBuilder().build("expo-001", incomplete)

    def test_empty_excerpt_list_raises_value_error(self):
        bad = {
            1: [_excerpt("Para 1")],
            2: [],  # empty
            3: [_excerpt("Para 3")],
            4: [_excerpt("Para 4")],
        }
        with pytest.raises(ValueError, match="empty excerpt list"):
            GroundingMapBuilder().build("expo-001", bad)
