"""test_traceability.py — Phase 014 CP4 traceability field tests.

Covers:
  - New GroundingMapEntry fields (source_ids, similarity_scores) with defaults
  - New GroundingMap field (retrieval_run_id) with default None
  - GroundingMapBuilder.build() populates traceability fields correctly
  - retrieval_run_id pass-through (caller-supplied only, never auto-generated)
  - Round-trip persistence via GroundingMapStore
  - Backward compatibility: existing callers without new params unchanged
"""
from __future__ import annotations

import pytest

from src.grounding_store.store import GroundingMapStore
from src.interfaces.rag import RetrievedExcerpt
from src.models.artifacts import GroundingMap, GroundingMapEntry
from src.rag.corpus import format_source_title, parse_source_id
from src.rag.grounding import GroundingMapBuilder

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RETRIEVAL_RUN_ID = "test-run-001"


def _make_excerpt(
    source_id: str,
    citation: str,
    text: str = "Some theological text.",
    relevance_score: float = 0.75,
) -> RetrievedExcerpt:
    return RetrievedExcerpt(
        text=text,
        source_title=format_source_title(source_id, citation),
        author="Matthew Henry",
        source_type="commentary",
        relevance_score=relevance_score,
    )


def _four_para_excerpts() -> dict:
    """Minimal valid paragraph_excerpts dict with one excerpt per paragraph."""
    return {
        1: [_make_excerpt("exc_commentary_001", "Commentary on Lamentations 3", relevance_score=0.80)],
        2: [_make_excerpt("exc_commentary_002", "Commentary on Matthew 5", relevance_score=0.65)],
        3: [_make_excerpt("exc_commentary_003", "Commentary on Romans 8", relevance_score=0.90)],
        4: [_make_excerpt("exc_commentary_004", "Commentary on Psalm 23", relevance_score=0.70)],
    }


def _valid_entry_kwargs(**overrides) -> dict:
    """Minimal kwargs to construct a valid GroundingMapEntry."""
    base = dict(
        paragraph_number=1,
        paragraph_name="declaration",
        sources_retrieved=["exc_commentary_001 | Commentary on Lamentations 3"],
        excerpts_used=["Some theological text."],
        how_retrieval_informed_paragraph="Retrieved 1 excerpt(s) from 1 source(s).",
    )
    base.update(overrides)
    return base


def _four_valid_entries() -> list:
    """Four minimal GroundingMapEntries for constructing a GroundingMap directly."""
    entries = []
    for i in range(1, 5):
        entries.append(
            GroundingMapEntry(
                paragraph_number=i,
                paragraph_name=f"para{i}",
                sources_retrieved=[f"exc_commentary_{i:03d} | Commentary {i}"],
                excerpts_used=[f"Excerpt text {i}."],
                how_retrieval_informed_paragraph=f"Retrieved 1 excerpt(s) from 1 source(s).",
            )
        )
    return entries


# ---------------------------------------------------------------------------
# 1. Default values for new fields
# ---------------------------------------------------------------------------


class TestNewFieldDefaults:
    def test_grounding_map_retrieval_run_id_default_is_none(self):
        gm = GroundingMap(
            id="some-uuid",
            exposition_id="expo-001",
            entries=_four_valid_entries(),
        )
        assert gm.retrieval_run_id is None

    def test_grounding_map_entry_source_ids_default_is_empty_list(self):
        entry = GroundingMapEntry(**_valid_entry_kwargs())
        assert entry.source_ids == []

    def test_grounding_map_entry_similarity_scores_default_is_empty_list(self):
        entry = GroundingMapEntry(**_valid_entry_kwargs())
        assert entry.similarity_scores == []

    def test_grounding_map_construction_without_new_fields_succeeds(self):
        """Backward compatibility: all existing construction patterns still work."""
        gm = GroundingMap(
            id="uuid-bwd-compat",
            exposition_id="expo-bwd",
            entries=_four_valid_entries(),
        )
        assert gm.retrieval_run_id is None
        for e in gm.entries:
            assert e.source_ids == []
            assert e.similarity_scores == []


# ---------------------------------------------------------------------------
# 2. Builder populates source_ids correctly
# ---------------------------------------------------------------------------


class TestBuilderSourceIds:
    def test_source_ids_parallel_to_excerpts_used(self):
        pe = _four_para_excerpts()
        builder = GroundingMapBuilder()
        gm = builder.build("expo-001", pe)

        for para_num in (1, 2, 3, 4):
            entry = gm.entries[para_num - 1]
            excerpts = pe[para_num]
            assert len(entry.source_ids) == len(excerpts)
            assert len(entry.source_ids) == len(entry.excerpts_used)

    def test_source_ids_match_parse_source_id(self):
        pe = _four_para_excerpts()
        builder = GroundingMapBuilder()
        gm = builder.build("expo-001", pe)

        for para_num in (1, 2, 3, 4):
            entry = gm.entries[para_num - 1]
            excerpts = pe[para_num]
            expected = [parse_source_id(e.source_title) for e in excerpts]
            assert entry.source_ids == expected

    def test_source_ids_with_multiple_excerpts_per_paragraph(self):
        pe = {
            1: [
                _make_excerpt("exc_commentary_001", "Commentary on Lamentations 3"),
                _make_excerpt("exc_commentary_002", "Commentary on Matthew 5"),
            ],
            2: [_make_excerpt("exc_commentary_003", "Commentary on Romans 8")],
            3: [_make_excerpt("exc_commentary_004", "Commentary on Psalm 23")],
            4: [_make_excerpt("exc_commentary_005", "Commentary on Isaiah 40")],
        }
        builder = GroundingMapBuilder()
        gm = builder.build("expo-multi", pe)

        entry1 = gm.entries[0]
        assert entry1.source_ids == ["exc_commentary_001", "exc_commentary_002"]
        assert len(entry1.source_ids) == 2

    def test_source_ids_not_deduplicated(self):
        """source_ids is parallel to excerpts_used — not deduplicated like sources_retrieved."""
        pe = {
            1: [
                _make_excerpt("exc_commentary_001", "Commentary on Lamentations 3", text="Text A."),
                _make_excerpt("exc_commentary_001", "Commentary on Lamentations 3", text="Text B."),
            ],
            2: [_make_excerpt("exc_commentary_002", "Commentary on Matthew 5")],
            3: [_make_excerpt("exc_commentary_003", "Commentary on Romans 8")],
            4: [_make_excerpt("exc_commentary_004", "Commentary on Psalm 23")],
        }
        builder = GroundingMapBuilder()
        gm = builder.build("expo-dup", pe)

        entry1 = gm.entries[0]
        # sources_retrieved is deduplicated (1 unique), but source_ids is per-excerpt (2 total)
        assert len(entry1.sources_retrieved) == 1
        assert len(entry1.source_ids) == 2
        assert entry1.source_ids == ["exc_commentary_001", "exc_commentary_001"]


# ---------------------------------------------------------------------------
# 3. Builder populates similarity_scores correctly
# ---------------------------------------------------------------------------


class TestBuilderSimilarityScores:
    def test_similarity_scores_parallel_to_excerpts_used(self):
        pe = _four_para_excerpts()
        builder = GroundingMapBuilder()
        gm = builder.build("expo-001", pe)

        for para_num in (1, 2, 3, 4):
            entry = gm.entries[para_num - 1]
            excerpts = pe[para_num]
            assert len(entry.similarity_scores) == len(excerpts)
            assert len(entry.similarity_scores) == len(entry.source_ids)

    def test_similarity_scores_match_relevance_scores(self):
        pe = _four_para_excerpts()
        builder = GroundingMapBuilder()
        gm = builder.build("expo-001", pe)

        expected_scores = {1: 0.80, 2: 0.65, 3: 0.90, 4: 0.70}
        for para_num in (1, 2, 3, 4):
            entry = gm.entries[para_num - 1]
            excerpts = pe[para_num]
            assert entry.similarity_scores == [e.relevance_score for e in excerpts]
            assert entry.similarity_scores[0] == pytest.approx(expected_scores[para_num])

    def test_similarity_scores_multiple_excerpts_in_order(self):
        pe = {
            1: [
                _make_excerpt("exc_commentary_001", "Commentary on Lamentations 3", relevance_score=0.91),
                _make_excerpt("exc_commentary_002", "Commentary on Matthew 5", relevance_score=0.55),
            ],
            2: [_make_excerpt("exc_commentary_003", "Commentary on Romans 8", relevance_score=0.77)],
            3: [_make_excerpt("exc_commentary_004", "Commentary on Psalm 23", relevance_score=0.60)],
            4: [_make_excerpt("exc_commentary_005", "Commentary on Isaiah 40", relevance_score=0.82)],
        }
        builder = GroundingMapBuilder()
        gm = builder.build("expo-scores", pe)

        entry1 = gm.entries[0]
        assert entry1.similarity_scores == pytest.approx([0.91, 0.55])


# ---------------------------------------------------------------------------
# 4 & 5. retrieval_run_id pass-through
# ---------------------------------------------------------------------------


class TestRetrievalRunId:
    def test_retrieval_run_id_stored_when_supplied(self):
        pe = _four_para_excerpts()
        builder = GroundingMapBuilder()
        gm = builder.build("expo-001", pe, retrieval_run_id=_RETRIEVAL_RUN_ID)
        assert gm.retrieval_run_id == _RETRIEVAL_RUN_ID

    def test_retrieval_run_id_is_none_when_omitted(self):
        pe = _four_para_excerpts()
        builder = GroundingMapBuilder()
        gm = builder.build("expo-001", pe)
        assert gm.retrieval_run_id is None

    def test_retrieval_run_id_is_not_empty_string_when_omitted(self):
        """Ensure omission yields None, not ''."""
        pe = _four_para_excerpts()
        builder = GroundingMapBuilder()
        gm = builder.build("expo-001", pe)
        assert gm.retrieval_run_id != ""

    def test_retrieval_run_id_with_paragraph_names_override(self):
        """retrieval_run_id works with optional paragraph_names param."""
        pe = _four_para_excerpts()
        builder = GroundingMapBuilder()
        gm = builder.build(
            "expo-001",
            pe,
            paragraph_names={1: "opening", 2: "history", 3: "doctrine", 4: "application"},
            retrieval_run_id=_RETRIEVAL_RUN_ID,
        )
        assert gm.retrieval_run_id == _RETRIEVAL_RUN_ID
        assert gm.entries[0].paragraph_name == "opening"


# ---------------------------------------------------------------------------
# 6. Constant string usage (static — verified by reviewing tests above)
#    All uses of retrieval_run_id in this file use _RETRIEVAL_RUN_ID = "test-run-001"
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 7. Existing GroundingMap construction works without new fields (bwd compat)
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_builder_without_new_params_produces_valid_map(self):
        pe = _four_para_excerpts()
        builder = GroundingMapBuilder()
        gm = builder.build("expo-bwd", pe)

        assert gm.exposition_id == "expo-bwd"
        assert len(gm.entries) == 4
        assert gm.retrieval_run_id is None

    def test_existing_entry_fields_unchanged(self):
        pe = _four_para_excerpts()
        builder = GroundingMapBuilder()
        gm = builder.build("expo-bwd", pe)

        for i, entry in enumerate(gm.entries, start=1):
            assert entry.paragraph_number == i
            assert isinstance(entry.sources_retrieved, list)
            assert len(entry.sources_retrieved) >= 1
            assert isinstance(entry.excerpts_used, list)
            assert len(entry.excerpts_used) >= 1
            assert entry.how_retrieval_informed_paragraph.startswith("Retrieved")

    def test_grounding_map_entry_direct_construction_without_new_fields(self):
        """Existing code constructing GroundingMapEntry without new fields works."""
        entry = GroundingMapEntry(
            paragraph_number=1,
            paragraph_name="declaration",
            sources_retrieved=["source_a | Some Citation"],
            excerpts_used=["Excerpt text."],
            how_retrieval_informed_paragraph="Retrieved 1 excerpt(s) from 1 source(s).",
        )
        assert entry.source_ids == []
        assert entry.similarity_scores == []


# ---------------------------------------------------------------------------
# 8. Round-trip via GroundingMapStore
# ---------------------------------------------------------------------------


class TestRoundTripPersistence:
    def test_round_trip_preserves_retrieval_run_id(self, monkeypatch, tmp_path):
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", tmp_path)

        pe = _four_para_excerpts()
        builder = GroundingMapBuilder()
        gm = builder.build("expo-rt", pe, retrieval_run_id=_RETRIEVAL_RUN_ID)

        store = GroundingMapStore(root_dir=tmp_path)
        store.save(gm)
        loaded = store.load(gm.id)

        assert loaded.retrieval_run_id == _RETRIEVAL_RUN_ID

    def test_round_trip_preserves_source_ids(self, monkeypatch, tmp_path):
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", tmp_path)

        pe = _four_para_excerpts()
        builder = GroundingMapBuilder()
        gm = builder.build("expo-rt", pe, retrieval_run_id=_RETRIEVAL_RUN_ID)

        store = GroundingMapStore(root_dir=tmp_path)
        store.save(gm)
        loaded = store.load(gm.id)

        assert loaded.entries[0].source_ids == gm.entries[0].source_ids

    def test_round_trip_preserves_similarity_scores(self, monkeypatch, tmp_path):
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", tmp_path)

        pe = _four_para_excerpts()
        builder = GroundingMapBuilder()
        gm = builder.build("expo-rt", pe, retrieval_run_id=_RETRIEVAL_RUN_ID)

        store = GroundingMapStore(root_dir=tmp_path)
        store.save(gm)
        loaded = store.load(gm.id)

        assert loaded.entries[0].similarity_scores == pytest.approx(
            gm.entries[0].similarity_scores
        )

    def test_round_trip_all_entries_preserved(self, monkeypatch, tmp_path):
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", tmp_path)

        pe = {
            1: [
                _make_excerpt("exc_commentary_001", "Commentary on Lamentations 3", relevance_score=0.80),
                _make_excerpt("exc_commentary_002", "Commentary on Matthew 5", relevance_score=0.65),
            ],
            2: [_make_excerpt("exc_commentary_003", "Commentary on Romans 8", relevance_score=0.90)],
            3: [_make_excerpt("exc_commentary_004", "Commentary on Psalm 23", relevance_score=0.70)],
            4: [_make_excerpt("exc_commentary_005", "Commentary on Isaiah 40", relevance_score=0.75)],
        }
        builder = GroundingMapBuilder()
        gm = builder.build("expo-all", pe, retrieval_run_id=_RETRIEVAL_RUN_ID)

        store = GroundingMapStore(root_dir=tmp_path)
        store.save(gm)
        loaded = store.load(gm.id)

        assert loaded.retrieval_run_id == _RETRIEVAL_RUN_ID
        for i in range(4):
            assert loaded.entries[i].source_ids == gm.entries[i].source_ids
            assert loaded.entries[i].similarity_scores == pytest.approx(
                gm.entries[i].similarity_scores
            )

    def test_round_trip_none_retrieval_run_id_preserved(self, monkeypatch, tmp_path):
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", tmp_path)

        pe = _four_para_excerpts()
        builder = GroundingMapBuilder()
        gm = builder.build("expo-none", pe)

        store = GroundingMapStore(root_dir=tmp_path)
        store.save(gm)
        loaded = store.load(gm.id)

        assert loaded.retrieval_run_id is None
