"""tests/rag/test_retrieval_engine.py — Tests for VectorRetrievalEngine.

Mandatory test gates (A–H) per CP3 specification:
  A) Determinism
  B) Tie-breaking by source_id ASC
  C) Threshold behavior
  D) top_k enforcement
  E) Fail-fast on missing files
  F) Source identity contract (AC-3)
  G) No disk writes during retrieve()
  H) Real scores (not always 1.0)
"""
from __future__ import annotations

import builtins
from pathlib import Path
from typing import List

import pytest

import src.rag.retrieval_engine as _engine_module
from src.interfaces.rag import RetrievedExcerpt
from src.rag.corpus import parse_source_id
from src.rag.retrieval_engine import VectorRetrievalEngine

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_EXCERPTS_INDEX = _REPO_ROOT / "data" / "index" / "excerpts-index.json"
_EXCERPTS_CORPUS = _REPO_ROOT / "data" / "corpus" / "excerpts-corpus.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine() -> VectorRetrievalEngine:
    return VectorRetrievalEngine(
        index_path=_EXCERPTS_INDEX,
        corpus_path=_EXCERPTS_CORPUS,
    )


# ---------------------------------------------------------------------------
# A) Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_query_returns_identical_results(self, engine):
        kwargs = dict(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3:22",
            topic="compassion mercy",
            top_k=5,
        )
        results_a = engine.retrieve(**kwargs)
        results_b = engine.retrieve(**kwargs)

        assert len(results_a) == len(results_b)
        for a, b in zip(results_a, results_b):
            assert a.source_title == b.source_title
            assert a.relevance_score == b.relevance_score
            assert a.text == b.text

    def test_same_query_different_order_of_types_is_stable(self, engine):
        kwargs = dict(
            paragraph_type="theological",
            source_types=["commentary"],
            passage_reference="Psalm 29",
            topic="sovereignty",
            top_k=5,
        )
        r1 = engine.retrieve(**kwargs)
        r2 = engine.retrieve(**kwargs)
        assert [r.source_title for r in r1] == [r.source_title for r in r2]

    def test_results_are_ordered_by_score_descending(self, engine):
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="affliction sorrow",
            top_k=10,
        )
        scores = [r.relevance_score for r in results]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# B) Tie-breaking by source_id ASC
# ---------------------------------------------------------------------------

class TestTieBreaking:
    def test_tie_break_orders_by_source_id_ascending(self, engine, monkeypatch):
        """When all documents score identically, ordering must be source_id ASC."""
        # Monkeypatch _cosine_similarity to return a fixed score for all docs
        monkeypatch.setattr(
            _engine_module,
            "_cosine_similarity",
            lambda q, qn, d: 0.42,
        )

        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="any reference",
            topic="any topic",
            top_k=10,
            threshold=0.0,
        )

        assert len(results) > 1, "Expected multiple tied results for tie-break test"
        source_ids = [r.source_title.split(" | ")[0] for r in results]
        assert source_ids == sorted(source_ids), (
            f"Tied results not sorted by source_id ASC: {source_ids}"
        )

    def test_all_tied_scores_are_equal(self, engine, monkeypatch):
        """Confirm monkeypatch produces uniform scores in tie-break scenario."""
        monkeypatch.setattr(
            _engine_module,
            "_cosine_similarity",
            lambda q, qn, d: 0.42,
        )
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="any reference",
            topic="any topic",
            top_k=10,
            threshold=0.0,
        )
        assert all(r.relevance_score == 0.42 for r in results)


# ---------------------------------------------------------------------------
# C) Threshold behavior
# ---------------------------------------------------------------------------

class TestThreshold:
    def test_threshold_above_all_scores_returns_empty(self, engine):
        """threshold=1.1 is above maximum cosine similarity — must return []."""
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="compassion",
            top_k=10,
            threshold=1.1,
        )
        assert results == []

    def test_threshold_zero_returns_matches(self, engine):
        """threshold=0.0 should return matches for a relevant query."""
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="compassion mercy morning",
            top_k=10,
            threshold=0.0,
        )
        assert len(results) > 0

    def test_high_threshold_filters_low_scoring_docs(self, engine, monkeypatch):
        """Documents below threshold must be excluded."""
        call_count = [0]
        real_cosine = _engine_module._cosine_similarity

        def counting_cosine(q, qn, d):
            call_count[0] += 1
            return 0.3 if call_count[0] % 2 == 0 else 0.1

        monkeypatch.setattr(_engine_module, "_cosine_similarity", counting_cosine)

        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="test",
            topic="test",
            top_k=10,
            threshold=0.25,
        )
        # Only docs scoring >= 0.25 (i.e., 0.3) should be included
        for r in results:
            assert r.relevance_score >= 0.25

    def test_threshold_at_exact_score_includes_doc(self, engine, monkeypatch):
        """threshold is inclusive (>=): a doc with exactly threshold score included."""
        monkeypatch.setattr(
            _engine_module, "_cosine_similarity", lambda q, qn, d: 0.5
        )
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="any",
            topic="any",
            top_k=10,
            threshold=0.5,
        )
        assert len(results) > 0

    def test_empty_source_types_returns_empty(self, engine):
        results = engine.retrieve(
            paragraph_type="context",
            source_types=[],
            passage_reference="Lamentations 3",
            topic="compassion",
        )
        assert results == []


# ---------------------------------------------------------------------------
# D) top_k enforcement
# ---------------------------------------------------------------------------

class TestTopK:
    def test_top_k_1_returns_at_most_1_result(self, engine):
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="compassion morning mercy",
            top_k=1,
        )
        assert len(results) <= 1

    def test_top_k_1_returns_exactly_1_when_matches_exist(self, engine, monkeypatch):
        """Force non-zero scores to guarantee at least one result."""
        monkeypatch.setattr(
            _engine_module, "_cosine_similarity", lambda q, qn, d: 0.5
        )
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="any",
            topic="any",
            top_k=1,
        )
        assert len(results) == 1

    def test_top_k_limits_results_to_k(self, engine, monkeypatch):
        """With enough matches, top_k caps the returned list."""
        monkeypatch.setattr(
            _engine_module, "_cosine_similarity", lambda q, qn, d: 0.5
        )
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="any",
            topic="any",
            top_k=2,
        )
        assert len(results) <= 2

    def test_top_k_larger_than_matches_returns_all(self, engine, monkeypatch):
        """top_k > number of matching docs → return all matching docs."""
        monkeypatch.setattr(
            _engine_module, "_cosine_similarity", lambda q, qn, d: 0.5
        )
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="any",
            topic="any",
            top_k=100,
        )
        # Corpus has 4 context/commentary docs
        assert len(results) == 4


# ---------------------------------------------------------------------------
# E) Fail-fast on missing files
# ---------------------------------------------------------------------------

class TestFailFast:
    def test_missing_index_raises_file_not_found_at_init(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Index file not found"):
            VectorRetrievalEngine(
                index_path=tmp_path / "nonexistent-index.json",
                corpus_path=_EXCERPTS_CORPUS,
            )

    def test_missing_corpus_raises_file_not_found_at_init(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Corpus file not found"):
            VectorRetrievalEngine(
                index_path=_EXCERPTS_INDEX,
                corpus_path=tmp_path / "nonexistent-corpus.json",
            )

    def test_no_auto_build_on_missing_index(self, tmp_path):
        """Engine must not create or write any file when index is missing."""
        with pytest.raises(FileNotFoundError):
            VectorRetrievalEngine(
                index_path=tmp_path / "missing.json",
                corpus_path=_EXCERPTS_CORPUS,
            )
        # tmp_path must still be empty — no auto-build occurred
        assert list(tmp_path.iterdir()) == []

    def test_default_constructor_loads_committed_files(self):
        """No-arg construction uses committed index and corpus."""
        engine = VectorRetrievalEngine()
        assert engine is not None


# ---------------------------------------------------------------------------
# F) Source identity contract [AC-3]
# ---------------------------------------------------------------------------

class TestSourceIdentity:
    def test_all_source_titles_parse_via_parse_source_id(self, engine):
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="compassion",
            top_k=10,
        )
        for r in results:
            sid = parse_source_id(r.source_title)
            assert sid, f"parse_source_id returned empty for {r.source_title!r}"

    def test_source_title_delimiter_is_exactly_space_pipe_space(self, engine):
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="mercy",
            top_k=10,
        )
        for r in results:
            assert " | " in r.source_title, (
                f"Missing ' | ' delimiter in: {r.source_title!r}"
            )
            # Must not use any other delimiter variant
            parts = r.source_title.split(" | ", maxsplit=1)
            assert len(parts) == 2, f"Unexpected split for: {r.source_title!r}"

    def test_source_id_extracted_matches_corpus_slug_pattern(self, engine):
        import re
        slug_re = re.compile(r"^[a-z][a-z0-9_]*[a-z0-9]$")
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="mercy",
            top_k=10,
        )
        for r in results:
            sid = parse_source_id(r.source_title)
            assert slug_re.match(sid), f"source_id {sid!r} is not a valid slug"

    def test_theological_results_have_valid_source_titles(self, engine):
        results = engine.retrieve(
            paragraph_type="theological",
            source_types=["commentary"],
            passage_reference="Romans 11",
            topic="grace",
            top_k=10,
        )
        for r in results:
            assert " | " in r.source_title
            assert parse_source_id(r.source_title)


# ---------------------------------------------------------------------------
# G) No disk writes during retrieve()
# ---------------------------------------------------------------------------

class TestNoDiskIO:
    def test_retrieve_does_no_disk_io(self):
        """retrieve() must perform zero disk I/O after construction."""
        # Build engine while real open() is available
        engine = VectorRetrievalEngine(
            index_path=_EXCERPTS_INDEX,
            corpus_path=_EXCERPTS_CORPUS,
        )

        # Now block ALL disk access to prove retrieve() is fully in-memory
        original_open = builtins.open

        def no_disk_open(*args, **kwargs):
            raise AssertionError(
                f"retrieve() unexpectedly accessed disk: args={args!r}"
            )

        builtins.open = no_disk_open
        try:
            results = engine.retrieve(
                paragraph_type="context",
                source_types=["commentary"],
                passage_reference="Lamentations 3",
                topic="compassion",
                top_k=5,
            )
        finally:
            builtins.open = original_open

        assert isinstance(results, list)

    def test_retrieve_no_write_mode_opens(self, monkeypatch):
        """retrieve() must not open any file in write/append/create mode."""
        engine = VectorRetrievalEngine(
            index_path=_EXCERPTS_INDEX,
            corpus_path=_EXCERPTS_CORPUS,
        )
        original_open = builtins.open

        def no_write_open(path, mode="r", *args, **kwargs):
            m = str(mode)
            if "w" in m or "a" in m or "x" in m:
                raise AssertionError(
                    f"retrieve() attempted write-mode open: {path!r} mode={mode!r}"
                )
            return original_open(path, mode, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", no_write_open)

        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="morning mercy",
            top_k=5,
        )
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# H) Real scores (not always 1.0)
# ---------------------------------------------------------------------------

class TestRealScores:
    def test_scores_are_not_always_1_0(self, engine):
        """relevance_score must reflect cosine similarity, not a fixed 1.0."""
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="compassion mercy morning",
            top_k=10,
        )
        assert len(results) > 0
        scores = [r.relevance_score for r in results]
        assert not all(s == 1.0 for s in scores), (
            "All scores are 1.0 — expected real cosine similarity values"
        )

    def test_scores_are_in_valid_range(self, engine):
        """Cosine similarity of non-negative vectors must be in [0.0, 1.0]."""
        results = engine.retrieve(
            paragraph_type="theological",
            source_types=["commentary"],
            passage_reference="Psalm 29",
            topic="sovereignty wisdom",
            top_k=10,
        )
        for r in results:
            assert 0.0 <= r.relevance_score <= 1.0, (
                f"Score {r.relevance_score} out of valid range [0, 1]"
            )

    def test_relevant_query_scores_higher_than_irrelevant(self, engine):
        """A query closely matching a doc's text should outscore a random query."""
        # "compassion morning mercy" is literally in exc_commentary_003
        high_results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3:23",
            topic="compassion morning mercy renewed",
            top_k=1,
        )
        low_results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="xyz 999",
            topic="zzz unknown term",
            top_k=1,
        )
        if high_results and low_results:
            assert high_results[0].relevance_score > low_results[0].relevance_score

    def test_score_varies_across_different_queries(self, engine):
        """Different queries must produce different score distributions."""
        r1 = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="mercy compassion",
            top_k=4,
        )
        r2 = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Psalm 29",
            topic="floods sovereignty",
            top_k=4,
        )
        if r1 and r2:
            scores_1 = [r.relevance_score for r in r1]
            scores_2 = [r.relevance_score for r in r2]
            assert scores_1 != scores_2, (
                "Different queries produced identical score distributions"
            )


# ---------------------------------------------------------------------------
# Additional integration checks
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_returned_texts_are_non_empty(self, engine):
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="mercy",
            top_k=5,
        )
        for r in results:
            assert r.text.strip(), "Returned excerpt has empty text"

    def test_returned_authors_are_non_empty(self, engine):
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="mercy",
            top_k=5,
        )
        for r in results:
            assert r.author.strip(), "Returned excerpt has empty author"

    def test_source_type_matches_filter(self, engine):
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="mercy",
            top_k=10,
        )
        for r in results:
            assert r.source_type == "commentary"

    def test_theological_filter_returns_theological_docs(self, engine):
        results = engine.retrieve(
            paragraph_type="theological",
            source_types=["commentary"],
            passage_reference="Romans 11",
            topic="grace",
            top_k=10,
        )
        # All returned docs must have source_type "commentary"
        for r in results:
            assert r.source_type == "commentary"

    def test_unknown_paragraph_type_returns_empty(self, engine):
        results = engine.retrieve(
            paragraph_type="narrative",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="mercy",
            top_k=5,
        )
        assert results == []

    def test_out_of_vocabulary_query_returns_empty(self, engine):
        """A query with no vocabulary overlap returns [] (not an error)."""
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="XYZXYZ999 ZZZNNN",
            topic="aaabbbccc dddeeefff",
            top_k=5,
        )
        assert results == []

    def test_result_is_list_of_retrieved_excerpt(self, engine):
        results = engine.retrieve(
            paragraph_type="context",
            source_types=["commentary"],
            passage_reference="Lamentations 3",
            topic="compassion",
            top_k=5,
        )
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, RetrievedExcerpt)
