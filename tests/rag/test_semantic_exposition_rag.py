"""tests/rag/test_semantic_exposition_rag.py — Phase 014 CP5 test gates.

Mandatory test gates (A–H) per CP5 specification:
  A) Determinism
  B) Interface compliance (structural — ExpositionRAGInterface is not runtime_checkable)
  C) Real similarity scores (not always 1.0 default)
  D) Source identity contract [AC-3]
  E) Shortage protocol (no match → returns [])
  F) No disk writes (retrieve_for_paragraph must not attempt any write-mode open)
  G) Fail-fast (missing index → FileNotFoundError at construction)
  H) Integration smoke with LLMExpositionGenerator (no pipeline wiring)
"""
from __future__ import annotations

import builtins
import inspect
from pathlib import Path
from typing import List

import pytest

from src.generation.llm_exposition_generator import LLMExpositionGenerator
from src.grounding_store.store import GroundingMapStore
from src.interfaces.rag import ExpositionRAGInterface, RetrievedExcerpt
from src.rag.corpus import parse_source_id
from src.rag.semantic_exposition_rag import SemanticExpositionRAG

# ---------------------------------------------------------------------------
# Repo paths (same convention as test_retrieval_engine.py)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_EXCERPTS_INDEX = _REPO_ROOT / "data" / "index" / "excerpts-index.json"
_EXCERPTS_CORPUS = _REPO_ROOT / "data" / "corpus" / "excerpts-corpus.json"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rag() -> SemanticExpositionRAG:
    """Module-scoped RAG instance backed by committed index and corpus."""
    return SemanticExpositionRAG(
        index_path=_EXCERPTS_INDEX,
        corpus_path=_EXCERPTS_CORPUS,
    )


# ---------------------------------------------------------------------------
# FakeLLMClient (for gate H integration smoke)
# ---------------------------------------------------------------------------

_FAKE_LLM_TEXT = "\n\n".join(
    [
        "declaration " + " ".join(["grace"] * 136),
        "context " + " ".join(["mercy"] * 136),
        "theological " + " ".join(["faith"] * 136),
        "bridge " + " ".join(["hope"] * 136),
    ]
)


class FakeLLMClient:
    """Deterministic LLM stub. Returns fixed exposition text."""

    def generate(self, prompt: str) -> str:
        return _FAKE_LLM_TEXT


# ---------------------------------------------------------------------------
# A) Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_call_returns_identical_results(self, rag):
        kwargs = dict(
            paragraph_type="context",
            passage_reference="Lamentations 3:22",
            topic="compassion mercy",
            source_types=["commentary"],
        )
        results_a = rag.retrieve_for_paragraph(**kwargs)
        results_b = rag.retrieve_for_paragraph(**kwargs)

        assert len(results_a) == len(results_b)
        for a, b in zip(results_a, results_b):
            assert a.source_title == b.source_title
            assert a.relevance_score == b.relevance_score
            assert a.text == b.text

    def test_theological_same_call_identical(self, rag):
        kwargs = dict(
            paragraph_type="theological",
            passage_reference="Romans 8:28",
            topic="grace faith",
            source_types=["commentary"],
        )
        r1 = rag.retrieve_for_paragraph(**kwargs)
        r2 = rag.retrieve_for_paragraph(**kwargs)

        assert [r.source_title for r in r1] == [r.source_title for r in r2]
        assert [r.relevance_score for r in r1] == [r.relevance_score for r in r2]

    def test_different_queries_may_differ(self, rag):
        """Sanity check: different inputs can yield different results."""
        r_context = rag.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="Lamentations 3:22",
            topic="compassion",
            source_types=["commentary"],
        )
        r_theological = rag.retrieve_for_paragraph(
            paragraph_type="theological",
            passage_reference="Romans 8",
            topic="grace",
            source_types=["commentary"],
        )
        # Results come from different paragraph_type buckets — must differ
        # (at minimum source_titles differ between context and theological docs)
        context_titles = {r.source_title for r in r_context}
        theological_titles = {r.source_title for r in r_theological}
        assert context_titles != theological_titles


# ---------------------------------------------------------------------------
# B) Interface compliance
# ---------------------------------------------------------------------------


class TestInterfaceCompliance:
    def test_has_retrieve_for_paragraph_method(self, rag):
        assert hasattr(rag, "retrieve_for_paragraph")
        assert callable(rag.retrieve_for_paragraph)

    def test_signature_matches_protocol(self):
        """SemanticExpositionRAG.retrieve_for_paragraph has exact protocol signature."""
        impl_sig = inspect.signature(SemanticExpositionRAG.retrieve_for_paragraph)
        proto_sig = inspect.signature(ExpositionRAGInterface.retrieve_for_paragraph)

        impl_params = list(impl_sig.parameters.keys())
        proto_params = list(proto_sig.parameters.keys())

        # Both should have the same parameter names
        assert impl_params == proto_params, (
            f"Parameter mismatch: impl={impl_params} proto={proto_params}"
        )

    def test_returns_list_of_retrieved_excerpts(self, rag):
        results = rag.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="Lamentations 3:22",
            topic="compassion",
            source_types=["commentary"],
        )
        assert isinstance(results, list)
        for item in results:
            assert isinstance(item, RetrievedExcerpt)

    def test_usable_as_rag_injection_target(self):
        """SemanticExpositionRAG can be duck-type injected wherever ExpositionRAGInterface is needed."""
        instance = SemanticExpositionRAG(
            index_path=_EXCERPTS_INDEX,
            corpus_path=_EXCERPTS_CORPUS,
        )
        # Verify the method is present and callable with protocol args
        result = instance.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="Psalm 23",
            topic="shepherd",
            source_types=["commentary"],
        )
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# C) Real similarity scores (not always 1.0 default)
# ---------------------------------------------------------------------------


class TestRealScores:
    def test_relevance_scores_are_not_always_default_1_0(self, rag):
        """Scores must reflect actual cosine similarity, not the 1.0 RetrievedExcerpt default."""
        results = rag.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="Lamentations 3:22",
            topic="compassion mercy morning",
            source_types=["commentary"],
        )
        assert len(results) > 0, "Expected at least one result for a matching query"
        scores = [r.relevance_score for r in results]
        assert not all(s == 1.0 for s in scores), (
            f"All scores are 1.0 (RetrievedExcerpt default) — real cosine scores expected. "
            f"Scores: {scores}"
        )

    def test_scores_are_in_range_0_to_1(self, rag):
        results = rag.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="Lamentations 3:22",
            topic="compassion mercy",
            source_types=["commentary"],
        )
        for r in results:
            assert 0.0 <= r.relevance_score <= 1.0, (
                f"Score {r.relevance_score} out of [0, 1] range"
            )

    def test_theological_scores_not_all_default(self, rag):
        results = rag.retrieve_for_paragraph(
            paragraph_type="theological",
            passage_reference="Romans 8",
            topic="grace faith righteousness",
            source_types=["commentary"],
        )
        assert len(results) > 0
        scores = [r.relevance_score for r in results]
        assert not all(s == 1.0 for s in scores)


# ---------------------------------------------------------------------------
# D) Source identity contract [AC-3]
# ---------------------------------------------------------------------------


class TestSourceIdentity:
    def test_all_source_titles_contain_delimiter(self, rag):
        results = rag.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="Lamentations 3:22",
            topic="compassion",
            source_types=["commentary"],
        )
        for r in results:
            assert " | " in r.source_title, (
                f"Missing ' | ' delimiter in source_title: {r.source_title!r}"
            )

    def test_all_source_titles_parse_via_parse_source_id(self, rag):
        results = rag.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="Lamentations 3:22",
            topic="compassion mercy",
            source_types=["commentary"],
        )
        for r in results:
            sid = parse_source_id(r.source_title)
            assert sid, f"parse_source_id returned empty for {r.source_title!r}"

    def test_exactly_one_delimiter_per_source_title(self, rag):
        results = rag.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="Lamentations 3:22",
            topic="mercy compassion morning",
            source_types=["commentary"],
        )
        for r in results:
            parts = r.source_title.split(" | ", maxsplit=1)
            assert len(parts) == 2, (
                f"Expected exactly one ' | ' in source_title: {r.source_title!r}"
            )

    def test_theological_source_titles_follow_contract(self, rag):
        results = rag.retrieve_for_paragraph(
            paragraph_type="theological",
            passage_reference="Romans 11",
            topic="grace",
            source_types=["commentary"],
        )
        for r in results:
            assert " | " in r.source_title
            sid = parse_source_id(r.source_title)
            assert sid


# ---------------------------------------------------------------------------
# E) Shortage protocol (no match → returns [])
# ---------------------------------------------------------------------------


class TestShortageProtocol:
    def test_threshold_above_max_returns_empty(self):
        """threshold=1.1 exceeds maximum cosine similarity — must return []."""
        rag_strict = SemanticExpositionRAG(
            index_path=_EXCERPTS_INDEX,
            corpus_path=_EXCERPTS_CORPUS,
            threshold=1.1,
        )
        results = rag_strict.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="Lamentations 3:22",
            topic="compassion",
            source_types=["commentary"],
        )
        assert results == []

    def test_empty_source_types_returns_empty(self, rag):
        """No source_types → VectorRetrievalEngine returns [] immediately."""
        results = rag.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="Lamentations 3:22",
            topic="compassion",
            source_types=[],
        )
        assert results == []

    def test_oov_query_returns_empty(self, rag):
        """Query with zero vocabulary overlap with index → returns []."""
        # Digits-only passage_reference + numeric topic — no word tokens in index vocab
        results = rag.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="1234567890",
            topic="9876543210",
            source_types=["commentary"],
        )
        assert results == []

    def test_shortage_result_is_plain_empty_list(self, rag):
        """Shortage protocol returns [] (not None, not a list with placeholders)."""
        results = rag.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="1234567890",
            topic="9876543210",
            source_types=[],
        )
        assert results == []
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# F) No disk writes during retrieve_for_paragraph()
# ---------------------------------------------------------------------------


class TestNoDiskWrites:
    def test_retrieve_for_paragraph_does_no_disk_io_after_init(self):
        """After construction, retrieve_for_paragraph() must be fully in-memory."""
        rag_instance = SemanticExpositionRAG(
            index_path=_EXCERPTS_INDEX,
            corpus_path=_EXCERPTS_CORPUS,
        )

        original_open = builtins.open

        def no_disk_open(*args, **kwargs):
            raise AssertionError(
                f"retrieve_for_paragraph() unexpectedly accessed disk: args={args!r}"
            )

        builtins.open = no_disk_open
        try:
            results = rag_instance.retrieve_for_paragraph(
                paragraph_type="context",
                passage_reference="Lamentations 3:22",
                topic="compassion",
                source_types=["commentary"],
            )
        finally:
            builtins.open = original_open

        assert isinstance(results, list)

    def test_no_write_mode_opens_during_retrieve(self, monkeypatch):
        """retrieve_for_paragraph() must not open any file in write/append/create mode."""
        rag_instance = SemanticExpositionRAG(
            index_path=_EXCERPTS_INDEX,
            corpus_path=_EXCERPTS_CORPUS,
        )
        original_open = builtins.open

        def no_write_open(path, mode="r", *args, **kwargs):
            m = str(mode)
            if "w" in m or "a" in m or "x" in m:
                raise AssertionError(
                    f"retrieve_for_paragraph() attempted write-mode open: "
                    f"{path!r} mode={mode!r}"
                )
            return original_open(path, mode, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", no_write_open)

        results = rag_instance.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="Lamentations 3:22",
            topic="mercy morning",
            source_types=["commentary"],
        )
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# G) Fail-fast at construction
# ---------------------------------------------------------------------------


class TestFailFast:
    def test_missing_index_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SemanticExpositionRAG(
                index_path=tmp_path / "nonexistent-index.json",
                corpus_path=_EXCERPTS_CORPUS,
            )

    def test_missing_corpus_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SemanticExpositionRAG(
                index_path=_EXCERPTS_INDEX,
                corpus_path=tmp_path / "nonexistent-corpus.json",
            )

    def test_fail_fast_before_any_disk_writes(self, tmp_path):
        """Construction failure must not create any files in tmp_path."""
        with pytest.raises(FileNotFoundError):
            SemanticExpositionRAG(
                index_path=tmp_path / "missing.json",
                corpus_path=_EXCERPTS_CORPUS,
            )
        assert list(tmp_path.iterdir()) == [], (
            "No files should be created on construction failure"
        )

    def test_error_message_mentions_index(self, tmp_path):
        """FileNotFoundError message should be informative about the missing index."""
        with pytest.raises(FileNotFoundError, match="(?i)index"):
            SemanticExpositionRAG(
                index_path=tmp_path / "missing-index.json",
                corpus_path=_EXCERPTS_CORPUS,
            )


# ---------------------------------------------------------------------------
# H) Integration smoke — LLMExpositionGenerator with SemanticExpositionRAG
# (NO pipeline wiring — generation_pipeline.py is untouched)
# ---------------------------------------------------------------------------


class TestIntegrationSmoke:
    def test_llm_exposition_generator_accepts_semantic_rag(
        self, tmp_path, monkeypatch
    ):
        """SemanticExpositionRAG can be injected into LLMExpositionGenerator."""
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", tmp_path)

        semantic_rag = SemanticExpositionRAG(
            index_path=_EXCERPTS_INDEX,
            corpus_path=_EXCERPTS_CORPUS,
        )
        gen = LLMExpositionGenerator(
            llm=FakeLLMClient(),
            rag=semantic_rag,
        )

        exposition = gen.generate_exposition(
            exposition_id="expo-semantic-smoke-001",
            topic="compassion",
            passage_reference="Lamentations 3:22",
        )

        assert exposition is not None

    def test_exposition_section_produced_with_truthy_grounding_map_id(
        self, tmp_path, monkeypatch
    ):
        """grounding_map_id must be truthy (GroundingMap artifact was saved)."""
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", tmp_path)

        semantic_rag = SemanticExpositionRAG(
            index_path=_EXCERPTS_INDEX,
            corpus_path=_EXCERPTS_CORPUS,
        )
        gen = LLMExpositionGenerator(
            llm=FakeLLMClient(),
            rag=semantic_rag,
        )

        exposition = gen.generate_exposition(
            exposition_id="expo-semantic-gm-001",
            topic="grace",
            passage_reference="Romans 8:28",
        )

        assert exposition.grounding_map_id, (
            "grounding_map_id must be truthy after generate_exposition()"
        )

    def test_grounding_map_artifact_persisted(self, tmp_path, monkeypatch):
        """GroundingMap artifact must be saved to the store during generation."""
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", tmp_path)

        semantic_rag = SemanticExpositionRAG(
            index_path=_EXCERPTS_INDEX,
            corpus_path=_EXCERPTS_CORPUS,
        )
        gen = LLMExpositionGenerator(
            llm=FakeLLMClient(),
            rag=semantic_rag,
        )

        exposition = gen.generate_exposition(
            exposition_id="expo-semantic-persist-001",
            topic="faith",
            passage_reference="Hebrews 11:1",
        )

        store = GroundingMapStore(root_dir=tmp_path)
        assert store.exists(exposition.grounding_map_id), (
            "GroundingMap artifact must exist in store after generation"
        )

    def test_grounding_map_has_real_source_titles(self, tmp_path, monkeypatch):
        """GroundingMap entries must reference real canonical source_titles from corpus."""
        monkeypatch.setattr(GroundingMapStore, "DEFAULT_ROOT", tmp_path)

        semantic_rag = SemanticExpositionRAG(
            index_path=_EXCERPTS_INDEX,
            corpus_path=_EXCERPTS_CORPUS,
        )
        gen = LLMExpositionGenerator(
            llm=FakeLLMClient(),
            rag=semantic_rag,
        )

        exposition = gen.generate_exposition(
            exposition_id="expo-semantic-titles-001",
            topic="compassion",
            passage_reference="Lamentations 3:22",
        )

        store = GroundingMapStore(root_dir=tmp_path)
        gm = store.load(exposition.grounding_map_id)

        for entry in gm.entries:
            for source_title in entry.sources_retrieved:
                if source_title != "RAG_SHORTAGE":
                    assert " | " in source_title, (
                        f"Non-shortage source_title missing ' | ': {source_title!r}"
                    )

    def test_generation_pipeline_not_modified(self):
        """Confirm generation_pipeline.py is not importing SemanticExpositionRAG."""
        import importlib
        import src.api.generation_pipeline as pipeline_module

        source = inspect.getsource(pipeline_module)
        assert "SemanticExpositionRAG" not in source, (
            "generation_pipeline.py must not reference SemanticExpositionRAG"
        )
        assert "semantic_exposition_rag" not in source, (
            "generation_pipeline.py must not import from semantic_exposition_rag"
        )
