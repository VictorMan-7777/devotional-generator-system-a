"""Unit tests for src/rag/exposition.py — ExpositionRAG.

Tests cover:
  - Protocol compliance (structural ExpositionRAGInterface assignment)
  - Return types: List[RetrievedExcerpt] with all required fields
  - paragraph_type filtering: "context" and "theological" routes
  - Fallback: unknown paragraph_type returns source_types-filtered results
  - Empty source_types returns []
  - Determinism: identical calls produce identical ordered results
  - Custom excerpts_path injection via tmp_path
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.interfaces.rag import ExpositionRAGInterface, RetrievedExcerpt
from src.rag.exposition import ExpositionRAG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_excerpts(tmp_path: Path, entries: list) -> Path:
    p = tmp_path / "excerpts.json"
    p.write_text(json.dumps(entries), encoding="utf-8")
    return p


_SAMPLE_ENTRY_CONTEXT = {
    "text": "Context excerpt text about covenant faithfulness.",
    "source_title": "Matthew Henry's Commentary",
    "author": "Matthew Henry",
    "source_type": "commentary",
    "paragraph_type": "context",
}

_SAMPLE_ENTRY_THEOLOGICAL = {
    "text": "Theological excerpt text about divine sovereignty.",
    "source_title": "Matthew Henry's Commentary",
    "author": "Matthew Henry",
    "source_type": "commentary",
    "paragraph_type": "theological",
}


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    def test_assignable_to_exposition_rag_interface(self):
        """ExpositionRAG must be structurally compatible with ExpositionRAGInterface."""
        rag: ExpositionRAGInterface = ExpositionRAG()
        assert rag is not None


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


class TestReturnType:
    def test_returns_list(self):
        result = ExpositionRAG().retrieve_for_paragraph(
            "context", "Lamentations 3:22", "grace", ["commentary"]
        )
        assert isinstance(result, list)

    def test_returns_retrieved_excerpts(self):
        result = ExpositionRAG().retrieve_for_paragraph(
            "context", "Lamentations 3:22", "grace", ["commentary"]
        )
        assert len(result) > 0
        assert all(isinstance(e, RetrievedExcerpt) for e in result)

    def test_all_required_fields_populated(self):
        result = ExpositionRAG().retrieve_for_paragraph(
            "context", "Lamentations 3:22", "grace", ["commentary"]
        )
        for e in result:
            assert e.text.strip()
            assert e.source_title.strip()
            assert e.author.strip()
            assert e.source_type.strip()


# ---------------------------------------------------------------------------
# Paragraph type filtering
# ---------------------------------------------------------------------------


class TestParagraphTypeFiltering:
    def test_context_paragraphs_returned(self):
        result = ExpositionRAG().retrieve_for_paragraph(
            "context", "Lamentations 3:22", "grace", ["commentary"]
        )
        assert len(result) > 0

    def test_theological_paragraphs_returned(self):
        result = ExpositionRAG().retrieve_for_paragraph(
            "theological", "Romans 8:28", "faith", ["commentary"]
        )
        assert len(result) > 0

    def test_context_and_theological_results_differ(self):
        context = ExpositionRAG().retrieve_for_paragraph(
            "context", "Lamentations 3:22", "grace", ["commentary"]
        )
        theological = ExpositionRAG().retrieve_for_paragraph(
            "theological", "Lamentations 3:22", "grace", ["commentary"]
        )
        context_texts = {e.text for e in context}
        theological_texts = {e.text for e in theological}
        # Seed has 4 context + 4 theological — no overlap expected.
        assert context_texts.isdisjoint(theological_texts)

    def test_unknown_paragraph_type_falls_back_to_source_types(self, tmp_path: Path):
        """Unrecognised paragraph_type falls back to source_type filtering."""
        p = _write_excerpts(
            tmp_path, [_SAMPLE_ENTRY_CONTEXT, _SAMPLE_ENTRY_THEOLOGICAL]
        )
        result = ExpositionRAG(p).retrieve_for_paragraph(
            "declaration",  # not "context" or "theological"
            "John 1:1",
            "grace",
            ["commentary"],
        )
        # Fallback returns all 2 entries since both have source_type="commentary"
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_source_types_returns_empty_list(self):
        result = ExpositionRAG().retrieve_for_paragraph(
            "context", "Lamentations 3:22", "grace", []
        )
        assert result == []

    def test_unknown_source_type_returns_empty_list(self, tmp_path: Path):
        p = _write_excerpts(tmp_path, [_SAMPLE_ENTRY_CONTEXT])
        result = ExpositionRAG(p).retrieve_for_paragraph(
            "context", "John 1:1", "grace", ["reference"]
        )
        assert result == []

    def test_empty_catalog_returns_empty_list(self, tmp_path: Path):
        p = _write_excerpts(tmp_path, [])
        result = ExpositionRAG(p).retrieve_for_paragraph(
            "context", "John 1:1", "grace", ["commentary"]
        )
        assert result == []


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_identical_calls_return_identical_order(self):
        rag = ExpositionRAG()
        result_a = rag.retrieve_for_paragraph(
            "theological", "Romans 8:28", "faith", ["commentary"]
        )
        result_b = rag.retrieve_for_paragraph(
            "theological", "Romans 8:28", "faith", ["commentary"]
        )
        assert [e.text for e in result_a] == [e.text for e in result_b]
