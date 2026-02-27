"""tests/rag/test_corpus.py — Tests for corpus schema, loader, and source_title formatter."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.rag.corpus import (
    CorpusDocument,
    format_source_title,
    load_corpus,
    parse_source_id,
    validate_corpus,
)

# ---------------------------------------------------------------------------
# Paths to corpus files
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_EXCERPTS_CORPUS = _REPO_ROOT / "data" / "corpus" / "excerpts-corpus.json"
_QUOTES_CORPUS = _REPO_ROOT / "data" / "corpus" / "quotes-corpus.json"

_VALID_SOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*[a-z0-9]$")


# ---------------------------------------------------------------------------
# format_source_title
# ---------------------------------------------------------------------------

class TestFormatSourceTitle:
    def test_produces_pipe_delimited_format(self):
        result = format_source_title("exc_commentary_001", "Commentary on Lamentations 3")
        assert result == "exc_commentary_001 | Commentary on Lamentations 3"

    def test_delimiter_is_exactly_space_pipe_space(self):
        result = format_source_title("some_id", "Some Citation")
        assert " | " in result
        assert result.index(" | ") == len("some_id")

    def test_source_id_is_first_component(self):
        sid = "exc_commentary_007"
        cit = "Commentary on Philippians 4:11 (Contentment)"
        result = format_source_title(sid, cit)
        assert result.startswith(sid + " | ")

    def test_citation_is_second_component(self):
        cit = "Commentary on Hebrews 11:1 (Faith)"
        result = format_source_title("exc_commentary_008", cit)
        assert result.endswith(" | " + cit)


# ---------------------------------------------------------------------------
# parse_source_id
# ---------------------------------------------------------------------------

class TestParseSourceId:
    def test_round_trip_with_format(self):
        sid = "exc_commentary_001"
        cit = "Commentary on Lamentations 3"
        assert parse_source_id(format_source_title(sid, cit)) == sid

    def test_round_trip_various_ids(self):
        pairs = [
            ("exc_commentary_003", "Commentary on Lamentations 3:23 (Morning Mercies)"),
            ("quot_chambers_009", "My Utmost for His Highest — February 14"),
            ("exc_commentary_008", "Commentary on Hebrews 11:1 (Faith)"),
        ]
        for sid, cit in pairs:
            assert parse_source_id(format_source_title(sid, cit)) == sid

    def test_raises_on_missing_delimiter(self):
        with pytest.raises(ValueError, match="source_title does not match"):
            parse_source_id("exc_commentary_001 Commentary on Lamentations 3")

    def test_raises_on_empty_string(self):
        with pytest.raises(ValueError):
            parse_source_id("")

    def test_raises_on_pipe_only_no_spaces(self):
        with pytest.raises(ValueError):
            parse_source_id("exc_id|citation")

    def test_raises_on_single_pipe_no_spaces(self):
        # Only ' | ' (space-pipe-space) is the valid delimiter
        with pytest.raises(ValueError):
            parse_source_id("exc_id|citation")


# ---------------------------------------------------------------------------
# Excerpts corpus file
# ---------------------------------------------------------------------------

class TestExcerptsCorpusFile:
    def test_loads_without_error(self):
        docs = load_corpus(_EXCERPTS_CORPUS)
        assert len(docs) == 8

    def test_source_ids_are_unique(self):
        docs = load_corpus(_EXCERPTS_CORPUS)
        ids = [d.source_id for d in docs]
        assert len(ids) == len(set(ids))

    def test_all_source_ids_are_valid_slugs(self):
        docs = load_corpus(_EXCERPTS_CORPUS)
        for doc in docs:
            assert _VALID_SOURCE_ID_RE.match(doc.source_id), (
                f"source_id {doc.source_id!r} is not a valid slug"
            )

    def test_all_paragraph_types_valid(self):
        docs = load_corpus(_EXCERPTS_CORPUS)
        valid = {"context", "theological"}
        for doc in docs:
            assert doc.paragraph_type in valid

    def test_all_source_types_valid(self):
        docs = load_corpus(_EXCERPTS_CORPUS)
        for doc in docs:
            assert doc.source_type in {"commentary", "reference"}

    def test_all_texts_non_empty(self):
        docs = load_corpus(_EXCERPTS_CORPUS)
        for doc in docs:
            assert doc.text.strip()

    def test_all_canonical_citations_non_empty(self):
        docs = load_corpus(_EXCERPTS_CORPUS)
        for doc in docs:
            assert doc.canonical_citation.strip()

    def test_all_source_titles_via_formatter(self):
        """All corpus entries produce valid source_title via formatter — no raw strings."""
        docs = load_corpus(_EXCERPTS_CORPUS)
        for doc in docs:
            st = format_source_title(doc.source_id, doc.canonical_citation)
            assert " | " in st
            assert parse_source_id(st) == doc.source_id

    def test_provenance_block_present_and_non_empty(self):
        with open(_EXCERPTS_CORPUS, encoding="utf-8") as fh:
            data = json.load(fh)
        assert "provenance" in data
        prov = data["provenance"]
        assert prov.get("corpus_version", "").strip()
        assert prov.get("created_date", "").strip()
        assert prov.get("license", "").strip()
        assert prov.get("notes", "").strip()

    def test_publication_year_is_1706(self):
        docs = load_corpus(_EXCERPTS_CORPUS)
        for doc in docs:
            assert doc.publication_year == 1706

    def test_context_and_theological_both_present(self):
        docs = load_corpus(_EXCERPTS_CORPUS)
        types = {d.paragraph_type for d in docs}
        assert "context" in types
        assert "theological" in types


# ---------------------------------------------------------------------------
# Quotes corpus file
# ---------------------------------------------------------------------------

class TestQuotesCorpusFile:
    def test_loads_without_error(self):
        docs = load_corpus(_QUOTES_CORPUS)
        assert len(docs) == 12

    def test_source_ids_are_unique(self):
        docs = load_corpus(_QUOTES_CORPUS)
        ids = [d.source_id for d in docs]
        assert len(ids) == len(set(ids))

    def test_all_source_ids_are_valid_slugs(self):
        docs = load_corpus(_QUOTES_CORPUS)
        for doc in docs:
            assert _VALID_SOURCE_ID_RE.match(doc.source_id), (
                f"source_id {doc.source_id!r} is not a valid slug"
            )

    def test_all_source_types_are_reference(self):
        docs = load_corpus(_QUOTES_CORPUS)
        for doc in docs:
            assert doc.source_type == "reference"

    def test_all_source_titles_via_formatter(self):
        docs = load_corpus(_QUOTES_CORPUS)
        for doc in docs:
            st = format_source_title(doc.source_id, doc.canonical_citation)
            assert parse_source_id(st) == doc.source_id

    def test_provenance_block_present_and_non_empty(self):
        with open(_QUOTES_CORPUS, encoding="utf-8") as fh:
            data = json.load(fh)
        assert "provenance" in data
        prov = data["provenance"]
        assert prov.get("corpus_version", "").strip()
        assert prov.get("notes", "").strip()

    def test_publication_year_is_1927(self):
        docs = load_corpus(_QUOTES_CORPUS)
        for doc in docs:
            assert doc.publication_year == 1927

    def test_source_ids_distinct_from_excerpts(self):
        """Quotes and excerpts source_ids must not collide."""
        exc_docs = load_corpus(_EXCERPTS_CORPUS)
        quot_docs = load_corpus(_QUOTES_CORPUS)
        exc_ids = {d.source_id for d in exc_docs}
        quot_ids = {d.source_id for d in quot_docs}
        assert exc_ids.isdisjoint(quot_ids), (
            f"source_id collision: {exc_ids & quot_ids}"
        )


# ---------------------------------------------------------------------------
# validate_corpus error cases
# ---------------------------------------------------------------------------

class TestValidateCorpusErrors:
    def _make_doc(self, **overrides) -> CorpusDocument:
        defaults = dict(
            source_id="exc_test_01",
            author="Author",
            work="Work",
            publication_year=2000,
            canonical_citation="Test citation",
            text="Some text here.",
            source_type="commentary",
            paragraph_type="context",
        )
        defaults.update(overrides)
        return CorpusDocument(**defaults)

    def test_empty_corpus_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            validate_corpus([])

    def test_duplicate_source_id_raises(self):
        doc1 = self._make_doc(source_id="exc_test_01")
        doc2 = self._make_doc(source_id="exc_test_01")
        with pytest.raises(ValueError, match="Duplicate source_id"):
            validate_corpus([doc1, doc2])

    def test_invalid_source_type_raises(self):
        doc = self._make_doc(source_type="unknown")
        with pytest.raises(ValueError, match="source_type"):
            validate_corpus([doc])

    def test_invalid_paragraph_type_raises(self):
        doc = self._make_doc(paragraph_type="narrative")
        with pytest.raises(ValueError, match="paragraph_type"):
            validate_corpus([doc])

    def test_empty_text_raises(self):
        doc = self._make_doc(text="   ")
        with pytest.raises(ValueError, match="text must not be empty"):
            validate_corpus([doc])

    def test_empty_canonical_citation_raises(self):
        doc = self._make_doc(canonical_citation="  ")
        with pytest.raises(ValueError, match="canonical_citation must not be empty"):
            validate_corpus([doc])


# ---------------------------------------------------------------------------
# load_corpus error cases
# ---------------------------------------------------------------------------

class TestLoadCorpusErrors:
    def test_missing_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_corpus(tmp_path / "nonexistent.json")

    def test_missing_documents_key_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"provenance": {}}), encoding="utf-8")
        with pytest.raises(ValueError, match="missing 'documents'"):
            load_corpus(p)

    def test_non_object_json_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(ValueError, match="must be an object"):
            load_corpus(p)

    def test_document_missing_required_field_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(
            json.dumps({
                "documents": [{"source_id": "exc_test_01", "author": "A"}]
            }),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Invalid corpus document"):
            load_corpus(p)


# ---------------------------------------------------------------------------
# CorpusDocument.source_title property
# ---------------------------------------------------------------------------

class TestCorpusDocumentSourceTitleProperty:
    def test_source_title_uses_formatter(self):
        doc = CorpusDocument(
            source_id="exc_commentary_001",
            author="Matthew Henry",
            work="Matthew Henry's Commentary on the Whole Bible",
            publication_year=1706,
            canonical_citation="Commentary on Lamentations 3",
            text="Some text.",
            source_type="commentary",
            paragraph_type="context",
        )
        assert doc.source_title == "exc_commentary_001 | Commentary on Lamentations 3"

    def test_source_title_parse_roundtrip(self):
        doc = CorpusDocument(
            source_id="quot_chambers_009",
            author="Oswald Chambers",
            work="My Utmost for His Highest",
            publication_year=1927,
            canonical_citation="My Utmost for His Highest — February 14",
            text="Some text.",
            source_type="reference",
            paragraph_type="theological",
        )
        assert parse_source_id(doc.source_title) == doc.source_id
