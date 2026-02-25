"""Unit tests for src/rag/catalog.py — QuoteCatalog.

Tests cover:
  - Protocol compliance (structural QuoteRAGInterface assignment)
  - Basic retrieval: return types, top_k clamping
  - Seed data integrity: all entries public_domain, non-empty
  - Shortage protocol: EMPTY and THIN warning categories
  - Determinism: identical calls produce identical ordered results
  - Scoring: relevance_score range, author_weights accepted without error
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.interfaces.rag import QuoteCandidate, QuoteRAGInterface
from src.rag.catalog import QuoteCatalog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_catalog(tmp_path: Path, entries: list) -> Path:
    p = tmp_path / "quotes.json"
    p.write_text(json.dumps(entries), encoding="utf-8")
    return p


_ONE_QUOTE = [
    {
        "quote_text": "Grace is sufficient for every need.",
        "author": "Oswald Chambers",
        "source_title": "My Utmost for His Highest",
        "publication_year": 1927,
        "page_or_url": "January 1",
        "public_domain": True,
    }
]

_TWO_QUOTES = _ONE_QUOTE + [
    {
        "quote_text": "Faith overcomes every obstacle in its path.",
        "author": "Oswald Chambers",
        "source_title": "My Utmost for His Highest",
        "publication_year": 1927,
        "page_or_url": "January 2",
        "public_domain": True,
    }
]


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    def test_assignable_to_quote_rag_interface(self):
        """QuoteCatalog must be structurally compatible with QuoteRAGInterface."""
        catalog: QuoteRAGInterface = QuoteCatalog()
        assert catalog is not None


# ---------------------------------------------------------------------------
# Basic retrieval
# ---------------------------------------------------------------------------


class TestBasicRetrieval:
    def test_returns_list(self):
        result = QuoteCatalog().retrieve_quotes("grace", "John 3:16")
        assert isinstance(result, list)

    def test_returns_quote_candidates(self):
        result = QuoteCatalog().retrieve_quotes("grace", "John 3:16")
        assert len(result) > 0
        assert all(isinstance(q, QuoteCandidate) for q in result)

    def test_top_k_1_returns_at_most_1(self):
        result = QuoteCatalog().retrieve_quotes("grace", "John 3:16", top_k=1)
        assert len(result) <= 1

    def test_top_k_3_returns_at_most_3(self):
        result = QuoteCatalog().retrieve_quotes("grace", "John 3:16", top_k=3)
        assert len(result) <= 3

    def test_default_top_k_returns_up_to_10(self):
        result = QuoteCatalog().retrieve_quotes("grace", "John 3:16")
        assert len(result) <= 10


# ---------------------------------------------------------------------------
# Seed data integrity
# ---------------------------------------------------------------------------


class TestSeedDataIntegrity:
    def test_all_seed_quotes_are_public_domain(self):
        result = QuoteCatalog().retrieve_quotes("grace", "John 3:16", top_k=100)
        assert all(q.public_domain is True for q in result)

    def test_seed_catalog_is_non_empty(self):
        result = QuoteCatalog().retrieve_quotes("grace", "John 3:16", top_k=100)
        assert len(result) > 0

    def test_all_required_fields_populated(self):
        result = QuoteCatalog().retrieve_quotes("grace", "John 3:16", top_k=100)
        for q in result:
            assert q.quote_text.strip()
            assert q.author.strip()
            assert q.source_title.strip()
            assert q.page_or_url.strip()


# ---------------------------------------------------------------------------
# Shortage protocol
# ---------------------------------------------------------------------------


class TestShortageProtocol:
    def test_thin_catalog_emits_thin_warning(self, tmp_path: Path):
        """1 or 2 available results → THIN warning."""
        p = _write_catalog(tmp_path, _ONE_QUOTE)
        with pytest.warns(UserWarning, match=r"\[RAG_SHORTAGE\]\[THIN\]"):
            result = QuoteCatalog(p).retrieve_quotes("grace", "John 3:16")
        assert len(result) == 1

    def test_thin_catalog_warning_contains_topic(self, tmp_path: Path):
        p = _write_catalog(tmp_path, _TWO_QUOTES)
        with pytest.warns(UserWarning, match=r"topic='surrender'"):
            QuoteCatalog(p).retrieve_quotes("surrender", "Romans 12:1")

    def test_empty_catalog_emits_empty_warning(self, tmp_path: Path):
        """0 results → EMPTY warning."""
        p = _write_catalog(tmp_path, [])
        with pytest.warns(UserWarning, match=r"\[RAG_SHORTAGE\]\[EMPTY\]"):
            result = QuoteCatalog(p).retrieve_quotes("grace", "John 3:16")
        assert result == []

    def test_thin_catalog_does_not_raise(self, tmp_path: Path):
        p = _write_catalog(tmp_path, _ONE_QUOTE)
        import warnings as _w
        with _w.catch_warnings():
            _w.simplefilter("ignore")
            result = QuoteCatalog(p).retrieve_quotes("grace", "John 3:16")
        assert isinstance(result, list)

    def test_full_catalog_no_warning(self):
        """12-quote seed catalog → at least 3 results → no shortage warning."""
        import warnings as _w
        with _w.catch_warnings():
            _w.simplefilter("error")  # any warning → error
            try:
                QuoteCatalog().retrieve_quotes("grace", "John 3:16", top_k=5)
            except UserWarning:
                pytest.fail("Unexpected shortage warning on full catalog")


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_identical_calls_return_identical_order(self):
        catalog = QuoteCatalog()
        result_a = catalog.retrieve_quotes("grace", "John 3:16", top_k=5)
        result_b = catalog.retrieve_quotes("grace", "John 3:16", top_k=5)
        assert [q.quote_text for q in result_a] == [q.quote_text for q in result_b]

    def test_different_topics_may_differ(self):
        """Sanity: at least verify both calls succeed without error."""
        catalog = QuoteCatalog()
        r1 = catalog.retrieve_quotes("grace", "Ephesians 2:8", top_k=3)
        r2 = catalog.retrieve_quotes("prayer", "Matthew 6:9", top_k=3)
        assert isinstance(r1, list)
        assert isinstance(r2, list)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestScoring:
    def test_relevance_score_within_valid_range(self):
        result = QuoteCatalog().retrieve_quotes("grace", "Ephesians 2:8", top_k=5)
        for q in result:
            assert 0.0 <= q.relevance_score <= 1.0

    def test_author_weights_accepted_without_error(self):
        result = QuoteCatalog().retrieve_quotes(
            "faith",
            "Hebrews 11:1",
            author_weights={"Oswald Chambers": 2.0},
            top_k=3,
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_zero_author_weight_drops_to_zero_score(self, tmp_path: Path):
        """Author with weight 0.0 → score of 0.0 regardless of keyword match."""
        p = _write_catalog(tmp_path, _TWO_QUOTES)
        import warnings as _w
        with _w.catch_warnings():
            _w.simplefilter("ignore")
            result = QuoteCatalog(p).retrieve_quotes(
                "grace",
                "John 3:16",
                author_weights={"Oswald Chambers": 0.0},
                top_k=5,
            )
        for q in result:
            assert q.relevance_score == 0.0
