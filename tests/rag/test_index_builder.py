"""tests/rag/test_index_builder.py — Tests for CorpusIndexBuilder."""
from __future__ import annotations

import builtins
import json
from pathlib import Path

import pytest

from src.rag.index_builder import CorpusIndexBuilder, _tokenize

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_EXCERPTS_CORPUS = _REPO_ROOT / "data" / "corpus" / "excerpts-corpus.json"
_EXCERPTS_INDEX = _REPO_ROOT / "data" / "index" / "excerpts-index.json"


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class TestTokenizer:
    def test_lowercase(self):
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_strips_punctuation(self):
        assert _tokenize("faith, hope; love.") == ["faith", "hope", "love"]

    def test_strips_apostrophe(self):
        assert _tokenize("God's grace") == ["gods", "grace"]

    def test_preserves_numbers(self):
        assert _tokenize("Psalm 29") == ["psalm", "29"]

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_whitespace_only(self):
        assert _tokenize("   ") == []

    def test_deterministic(self):
        text = "The Lord's compassions do not fail."
        assert _tokenize(text) == _tokenize(text)


# ---------------------------------------------------------------------------
# build() — basic structure
# ---------------------------------------------------------------------------

class TestBuildStructure:
    def test_schema_version_present(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        assert index["schema_version"] == "1.0.0"

    def test_num_documents_is_8(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        assert index["num_documents"] == 8
        assert len(index["documents"]) == 8

    def test_vocabulary_is_list(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        assert isinstance(index["vocabulary"], list)

    def test_idf_is_dict(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        assert isinstance(index["idf"], dict)

    def test_corpus_file_is_relative_path(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        # Must be a relative path (no absolute home-directory paths)
        assert not Path(index["corpus_file"]).is_absolute()
        assert index["corpus_file"] == "data/corpus/excerpts-corpus.json"

    def test_corpus_version_matches_provenance(self):
        with open(_EXCERPTS_CORPUS, encoding="utf-8") as fh:
            raw = json.load(fh)
        expected_version = raw["provenance"]["corpus_version"]

        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)

        assert index["corpus_version"] == expected_version

    def test_document_entries_have_required_fields(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        for entry in index["documents"]:
            assert "source_id" in entry
            assert "source_title" in entry
            assert "paragraph_type" in entry
            assert "source_type" in entry
            assert "tfidf" in entry

    def test_document_source_titles_contain_pipe_delimiter(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        for entry in index["documents"]:
            assert " | " in entry["source_title"]


# ---------------------------------------------------------------------------
# build() — vocabulary properties
# ---------------------------------------------------------------------------

class TestVocabulary:
    def test_vocabulary_is_sorted(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        vocab = index["vocabulary"]
        assert vocab == sorted(vocab)

    def test_vocabulary_has_no_duplicates(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        vocab = index["vocabulary"]
        assert len(vocab) == len(set(vocab))

    def test_vocabulary_is_non_empty(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        assert len(index["vocabulary"]) > 0

    def test_vocabulary_tokens_are_lowercase_alphanumeric(self):
        import re
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        pattern = re.compile(r"^[a-z0-9]+$")
        for token in index["vocabulary"]:
            assert pattern.match(token), f"Token {token!r} is not lowercase alphanumeric"

    def test_all_idf_terms_in_vocabulary(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        vocab_set = set(index["vocabulary"])
        for term in index["idf"]:
            assert term in vocab_set


# ---------------------------------------------------------------------------
# build() — IDF properties
# ---------------------------------------------------------------------------

class TestIDF:
    def test_all_idf_values_non_negative(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        for term, val in index["idf"].items():
            assert val >= 0, f"IDF for {term!r} is negative: {val}"

    def test_all_idf_values_at_least_1(self):
        # Smoothed IDF formula: log((N+1)/(df+1)) + 1 >= 1 always
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        for term, val in index["idf"].items():
            assert val >= 1.0, f"IDF for {term!r} < 1.0: {val}"

    def test_idf_values_rounded_to_10_decimal_places(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        for term, val in index["idf"].items():
            assert round(val, 10) == val, (
                f"IDF for {term!r}: {val!r} is not rounded to 10dp"
            )

    def test_idf_rare_term_higher_than_common_term(self):
        # A term appearing in 1 doc should have higher IDF than one in all 8
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        idf = index["idf"]
        # "and" appears in many docs; rare terms should score higher
        common_term = "and"
        if common_term in idf:
            some_rare = [t for t, v in idf.items() if v > idf[common_term]]
            assert len(some_rare) > 0, "Expected some terms to have higher IDF than 'and'"


# ---------------------------------------------------------------------------
# build() — TF-IDF properties
# ---------------------------------------------------------------------------

class TestTFIDF:
    def test_tfidf_values_rounded_to_10_decimal_places(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        for entry in index["documents"]:
            for term, val in entry["tfidf"].items():
                assert round(val, 10) == val, (
                    f"TF-IDF for {term!r} in {entry['source_id']!r}: "
                    f"{val!r} is not rounded to 10dp"
                )

    def test_tfidf_values_non_negative(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        for entry in index["documents"]:
            for term, val in entry["tfidf"].items():
                assert val >= 0, (
                    f"TF-IDF for {term!r} in {entry['source_id']!r} is negative: {val}"
                )

    def test_tfidf_terms_subset_of_vocabulary(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        vocab_set = set(index["vocabulary"])
        for entry in index["documents"]:
            for term in entry["tfidf"]:
                assert term in vocab_set, (
                    f"TF-IDF term {term!r} not in vocabulary"
                )

    def test_each_document_has_nonzero_tfidf(self):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        for entry in index["documents"]:
            assert len(entry["tfidf"]) > 0, (
                f"Document {entry['source_id']!r} has empty TF-IDF vector"
            )


# ---------------------------------------------------------------------------
# build() — determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_build_twice_produces_identical_output(self):
        builder = CorpusIndexBuilder()
        index_a = builder.build(_EXCERPTS_CORPUS)
        index_b = builder.build(_EXCERPTS_CORPUS)
        # Compare via JSON serialization (handles float equality reliably)
        import json
        assert json.dumps(index_a, sort_keys=True) == json.dumps(index_b, sort_keys=True)

    def test_build_produces_deterministic_vocabulary_order(self):
        builder = CorpusIndexBuilder()
        vocab_a = builder.build(_EXCERPTS_CORPUS)["vocabulary"]
        vocab_b = builder.build(_EXCERPTS_CORPUS)["vocabulary"]
        assert vocab_a == vocab_b

    def test_build_produces_deterministic_document_order(self):
        builder = CorpusIndexBuilder()
        docs_a = [e["source_id"] for e in builder.build(_EXCERPTS_CORPUS)["documents"]]
        docs_b = [e["source_id"] for e in builder.build(_EXCERPTS_CORPUS)["documents"]]
        assert docs_a == docs_b


# ---------------------------------------------------------------------------
# build() — no disk writes
# ---------------------------------------------------------------------------

class TestBuildNoDiskWrites:
    def test_build_does_not_write_files(self, monkeypatch):
        """build() must not open any file in write/append/create mode."""
        original_open = builtins.open

        def intercepted_open(path, mode="r", *args, **kwargs):
            m = str(mode)
            if "w" in m or "a" in m or "x" in m:
                raise AssertionError(
                    f"build() attempted to open for writing: {path!r} mode={mode!r}"
                )
            return original_open(path, mode, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", intercepted_open)

        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        assert index is not None
        assert index["num_documents"] == 8


# ---------------------------------------------------------------------------
# save() and load()
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_save_creates_file(self, tmp_path):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        index_path = tmp_path / "test-index.json"
        builder.save(index, index_path)
        assert index_path.exists()

    def test_save_creates_parent_dirs(self, tmp_path):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        index_path = tmp_path / "nested" / "subdir" / "index.json"
        builder.save(index, index_path)
        assert index_path.exists()

    def test_saved_file_is_valid_json(self, tmp_path):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        index_path = tmp_path / "index.json"
        builder.save(index, index_path)
        with open(index_path, encoding="utf-8") as fh:
            loaded = json.load(fh)
        assert loaded["schema_version"] == "1.0.0"

    def test_save_then_load_round_trips(self, tmp_path):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        index_path = tmp_path / "index.json"
        builder.save(index, index_path)
        loaded = builder.load(index_path)
        # Compare via JSON serialization for reliable float equality
        assert json.dumps(index, sort_keys=True) == json.dumps(loaded, sort_keys=True)

    def test_save_uses_sort_keys(self, tmp_path):
        builder = CorpusIndexBuilder()
        index = builder.build(_EXCERPTS_CORPUS)
        index_path = tmp_path / "index.json"
        builder.save(index, index_path)
        text = index_path.read_text(encoding="utf-8")
        data = json.loads(text)
        # Top-level keys should be in sorted order in the raw text
        top_keys_in_text = [k for k in data.keys()]
        assert top_keys_in_text == sorted(top_keys_in_text)

    def test_load_missing_file_raises_file_not_found(self, tmp_path):
        builder = CorpusIndexBuilder()
        with pytest.raises(FileNotFoundError):
            builder.load(tmp_path / "nonexistent.json")

    def test_load_invalid_missing_key_raises_value_error(self, tmp_path):
        index_path = tmp_path / "bad.json"
        index_path.write_text(json.dumps({"schema_version": "1.0.0"}), encoding="utf-8")
        builder = CorpusIndexBuilder()
        with pytest.raises(ValueError, match="missing required key"):
            builder.load(index_path)


# ---------------------------------------------------------------------------
# Committed excerpts-index.json validation
# ---------------------------------------------------------------------------

class TestCommittedIndex:
    def test_committed_index_exists(self):
        assert _EXCERPTS_INDEX.exists(), f"Committed index not found: {_EXCERPTS_INDEX}"

    def test_committed_index_loads_cleanly(self):
        builder = CorpusIndexBuilder()
        index = builder.load(_EXCERPTS_INDEX)
        assert index["schema_version"] == "1.0.0"

    def test_committed_index_has_8_documents(self):
        builder = CorpusIndexBuilder()
        index = builder.load(_EXCERPTS_INDEX)
        assert index["num_documents"] == 8

    def test_committed_index_corpus_file_no_absolute_path(self):
        builder = CorpusIndexBuilder()
        index = builder.load(_EXCERPTS_INDEX)
        assert not Path(index["corpus_file"]).is_absolute()

    def test_committed_index_matches_fresh_build(self):
        """Committed index must match a fresh build from current corpus."""
        builder = CorpusIndexBuilder()
        fresh = builder.build(_EXCERPTS_CORPUS)
        committed = builder.load(_EXCERPTS_INDEX)
        # Compare via JSON serialization
        assert json.dumps(fresh, sort_keys=True) == json.dumps(committed, sort_keys=True), (
            "Committed index is out of sync with corpus. Run scripts/rag/build-index.py."
        )
