"""
Scripture retrieval tests — FR-57 through FR-60.

All HTTP calls are intercepted via injected mock HttpClient.
No live network calls are made in this test suite.

Coverage:
  - Reference parsing (single verse, multi-verse, abbreviations, error cases)
  - FR-58 deterministic validation (book/chapter/verse match, HTML stripping)
  - Bolls.life primary: success, HTML stripping, 500 → retry → success
  - FR-59 fallback chain ordering (bolls → api.bible → operator import → alert)
  - API key absent: API.Bible step skipped entirely
  - Operator import CSV: case-insensitive lookup, missing reference, bypassed on success
  - Full-failure structured alert (FailureMode.ALL_SOURCES_EXHAUSTED)
  - Unparseable reference alert (FailureMode.UNPARSEABLE_REFERENCE)
"""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.scripture.retrieval import (
    FailureMode,
    HttpClient,
    ScriptureFailureAlert,
    ScriptureResult,
    ScriptureRetriever,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status_code: int, json_data=None) -> MagicMock:
    """Build a mock httpx.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    return resp


def _bolls_verse(book: int, chapter: int, verse: int, text: str) -> dict:
    """Return a minimal Bolls.life verse payload (list-element format)."""
    return {"pk": 1, "verse": verse, "text": text, "book": book, "chapter": chapter}


def _make_retriever(
    side_effects: list,
    api_bible_key: str | None = None,
) -> ScriptureRetriever:
    """Construct a ScriptureRetriever with a mock HttpClient."""
    http_client = MagicMock(spec=HttpClient)
    http_client.get.side_effect = side_effects
    return ScriptureRetriever(http_client=http_client, api_bible_key=api_bible_key)


def _make_csv(rows: list[dict], tmp_path: Path) -> Path:
    """Write a minimal operator-import CSV and return its path."""
    csv_path = tmp_path / "import.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["reference", "translation", "text"])
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


# ---------------------------------------------------------------------------
# TestParseReference
# ---------------------------------------------------------------------------


class TestParseReference:
    def test_single_verse(self):
        parsed = ScriptureRetriever._parse_reference("Romans 8:15")
        assert parsed.book_name == "Romans"
        assert parsed.book_id == 45
        assert parsed.chapter == 8
        assert parsed.verses == [15]

    def test_multi_verse_range(self):
        parsed = ScriptureRetriever._parse_reference("1 Corinthians 13:4-7")
        assert parsed.book_id == 46
        assert parsed.chapter == 13
        assert parsed.verses == [4, 5, 6, 7]

    def test_numbered_book(self):
        parsed = ScriptureRetriever._parse_reference("1 John 4:8")
        assert parsed.book_id == 62
        assert parsed.verses == [8]

    def test_book_abbreviation(self):
        parsed = ScriptureRetriever._parse_reference("Rom 8:15")
        assert parsed.book_id == 45
        assert parsed.chapter == 8
        assert parsed.verses == [15]

    def test_invalid_format_raises_value_error(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            ScriptureRetriever._parse_reference("Romans")

    def test_unknown_book_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown book"):
            ScriptureRetriever._parse_reference("Snargbok 1:1")


# ---------------------------------------------------------------------------
# TestValidateMatch
# ---------------------------------------------------------------------------


class TestValidateMatch:
    def _retriever(self) -> ScriptureRetriever:
        return ScriptureRetriever()

    def test_valid_match_returns_true(self):
        retriever = self._retriever()
        response = _bolls_verse(45, 8, 15, "For you have not received a spirit of slavery")
        assert retriever.validate_match(response, "Romans 8:15", "NASB") is True

    def test_wrong_book_returns_false(self):
        retriever = self._retriever()
        response = _bolls_verse(1, 8, 15, "some text")  # book_id=1 (Genesis), not Romans
        assert retriever.validate_match(response, "Romans 8:15", "NASB") is False

    def test_wrong_chapter_returns_false(self):
        retriever = self._retriever()
        response = _bolls_verse(45, 9, 15, "some text")  # chapter 9, not 8
        assert retriever.validate_match(response, "Romans 8:15", "NASB") is False

    def test_wrong_verse_returns_false(self):
        retriever = self._retriever()
        response = _bolls_verse(45, 8, 16, "some text")  # verse 16, not 15
        assert retriever.validate_match(response, "Romans 8:15", "NASB") is False

    def test_empty_text_returns_false(self):
        retriever = self._retriever()
        response = _bolls_verse(45, 8, 15, "")
        assert retriever.validate_match(response, "Romans 8:15", "NASB") is False

    def test_html_only_text_returns_false(self):
        retriever = self._retriever()
        response = _bolls_verse(45, 8, 15, "<b><i></i></b>")
        assert retriever.validate_match(response, "Romans 8:15", "NASB") is False

    def test_html_wrapped_text_returns_true(self):
        retriever = self._retriever()
        response = _bolls_verse(45, 8, 15, "<b>Spirit of adoption</b>")
        assert retriever.validate_match(response, "Romans 8:15", "NASB") is True

    def test_verse_in_multi_verse_range_matches(self):
        retriever = self._retriever()
        response = _bolls_verse(45, 8, 16, "some text")  # verse 16 is within 8:15-17
        assert retriever.validate_match(response, "Romans 8:15-17", "NASB") is True

    def test_verse_outside_range_returns_false(self):
        retriever = self._retriever()
        response = _bolls_verse(45, 8, 20, "some text")  # verse 20 not in 8:15-17
        assert retriever.validate_match(response, "Romans 8:15-17", "NASB") is False

    def test_unparseable_reference_returns_false(self):
        retriever = self._retriever()
        response = _bolls_verse(45, 8, 15, "some text")
        assert retriever.validate_match(response, "not a reference", "NASB") is False


# ---------------------------------------------------------------------------
# TestHtmlStripping
# ---------------------------------------------------------------------------


class TestHtmlStripping:
    def test_strips_single_tag(self):
        assert ScriptureRetriever._strip_html("<b>text</b>") == "text"

    def test_strips_nested_tags(self):
        assert ScriptureRetriever._strip_html("<b><i>text</i></b>") == "text"

    def test_no_tags_unchanged(self):
        assert ScriptureRetriever._strip_html("plain text") == "plain text"

    def test_preserves_text_around_tags(self):
        result = ScriptureRetriever._strip_html("before <em>middle</em> after")
        assert result == "before middle after"

    def test_empty_string(self):
        assert ScriptureRetriever._strip_html("") == ""


# ---------------------------------------------------------------------------
# TestBollsLifeRetrieval
# ---------------------------------------------------------------------------


class TestBollsLifeRetrieval:
    def test_successful_single_verse(self):
        verse_data = _bolls_verse(45, 8, 15, "Spirit of adoption text here")
        retriever = _make_retriever([_mock_response(200, [verse_data])])
        result = retriever.retrieve("Romans 8:15", "NASB")
        assert isinstance(result, ScriptureResult)
        assert result.text == "Spirit of adoption text here"
        assert result.translation == "NASB"
        assert result.retrieval_source == "bolls_life"
        assert result.reference == "Romans 8:15"
        assert result.verification_status == "verified"

    def test_successful_multi_verse_concatenates_with_space(self):
        verse15 = _bolls_verse(45, 8, 15, "Verse fifteen text.")
        verse16 = _bolls_verse(45, 8, 16, "Verse sixteen text.")
        retriever = _make_retriever([
            _mock_response(200, [verse15]),
            _mock_response(200, [verse16]),
        ])
        result = retriever.retrieve("Romans 8:15-16", "NASB")
        assert isinstance(result, ScriptureResult)
        assert result.text == "Verse fifteen text. Verse sixteen text."
        assert result.reference == "Romans 8:15-16"

    def test_html_stripped_from_returned_text(self):
        verse_data = _bolls_verse(45, 8, 15, "<b>Spirit</b> of <i>adoption</i>")
        retriever = _make_retriever([_mock_response(200, [verse_data])])
        result = retriever.retrieve("Romans 8:15", "NASB")
        assert isinstance(result, ScriptureResult)
        assert "<" not in result.text
        assert result.text == "Spirit of adoption"

    def test_single_http_500_triggers_retry_then_succeeds(self):
        """First attempt returns 500 → retry → 200 → ScriptureResult (FR-59a)."""
        verse_data = _bolls_verse(45, 8, 15, "Spirit of adoption")
        retriever = _make_retriever([
            _mock_response(500),               # first attempt fails
            _mock_response(200, [verse_data]), # retry succeeds
        ])
        result = retriever.retrieve("Romans 8:15", "NASB")
        assert isinstance(result, ScriptureResult)
        assert result.retrieval_source == "bolls_life"

    def test_two_500s_exhaust_bolls_life(self):
        """Both Bolls.life attempts fail; no key → ScriptureFailureAlert."""
        retriever = _make_retriever([
            _mock_response(500),  # first attempt
            _mock_response(500),  # retry
        ])
        result = retriever.retrieve("Romans 8:15", "NASB")
        assert isinstance(result, ScriptureFailureAlert)
        assert "bolls_life" in result.attempted_sources
        assert result.failure_mode == FailureMode.ALL_SOURCES_EXHAUSTED

    def test_wrong_verse_data_fails_validation(self):
        """200 response with wrong book data → validate_match fails → both retries fail."""
        wrong_verse = _bolls_verse(1, 1, 1, "In the beginning")  # Genesis 1:1
        retriever = _make_retriever([
            _mock_response(200, [wrong_verse]),  # first: passes HTTP but fails FR-58
            _mock_response(200, [wrong_verse]),  # retry: same
        ])
        result = retriever.retrieve("Romans 8:15", "NASB")
        assert isinstance(result, ScriptureFailureAlert)


# ---------------------------------------------------------------------------
# TestFallbackChain — FR-59 priority ordering
# ---------------------------------------------------------------------------


class TestFallbackChain:
    def test_api_bible_used_when_primary_fails_and_key_present(self):
        """Bolls.life both attempts fail → API.Bible succeeds (FR-59b)."""
        api_bible_data = {"data": {"content": "Spirit of adoption API.Bible text"}}
        retriever = _make_retriever(
            side_effects=[
                _mock_response(500),                      # bolls first attempt
                _mock_response(500),                      # bolls retry
                _mock_response(200, api_bible_data),      # api.bible
            ],
            api_bible_key="test-api-key-12345",
        )
        result = retriever.retrieve("Romans 8:15", "NASB")
        assert isinstance(result, ScriptureResult)
        assert result.retrieval_source == "api_bible"
        assert "Spirit of adoption API.Bible text" in result.text

    def test_api_bible_skipped_when_no_key(self):
        """No API key → api.bible step skipped entirely; goes straight to failure."""
        retriever = _make_retriever([
            _mock_response(500),
            _mock_response(500),
        ])
        result = retriever.retrieve("Romans 8:15", "NASB")
        assert isinstance(result, ScriptureFailureAlert)
        assert "api_bible" not in result.attempted_sources
        assert "bolls_life" in result.attempted_sources

    def test_operator_import_fallback_after_bolls_failure(self, tmp_path):
        """Bolls.life fails; operator import CSV has the verse → ScriptureResult (FR-59c)."""
        csv_path = _make_csv(
            [{"reference": "Romans 8:15", "translation": "NASB", "text": "Operator import text"}],
            tmp_path,
        )
        retriever = _make_retriever([
            _mock_response(500),
            _mock_response(500),
        ])
        result = retriever.retrieve("Romans 8:15", "NASB", operator_import=csv_path)
        assert isinstance(result, ScriptureResult)
        assert result.retrieval_source == "operator_import"
        assert result.text == "Operator import text"

    def test_all_sources_exhausted_returns_structured_alert(self, tmp_path):
        """Bolls fails, no key, CSV missing verse → ScriptureFailureAlert (FR-59d–f)."""
        csv_path = _make_csv(
            [{"reference": "John 3:16", "translation": "NASB", "text": "For God so loved"}],
            tmp_path,
        )
        retriever = _make_retriever([
            _mock_response(500),
            _mock_response(500),
        ])
        result = retriever.retrieve("Romans 8:15", "NASB", operator_import=csv_path)
        assert isinstance(result, ScriptureFailureAlert)
        assert result.failure_mode == FailureMode.ALL_SOURCES_EXHAUSTED
        assert result.reference == "Romans 8:15"
        assert result.translation == "NASB"
        assert "bolls_life" in result.attempted_sources
        assert "operator_import" in result.attempted_sources

    def test_full_chain_attempted_sources_order(self, tmp_path):
        """All three sources fail → attempted_sources lists them in FR-59 order."""
        csv_path = _make_csv([], tmp_path)  # header only, no data rows
        api_bible_data = {"data": {}}       # no 'content' key → empty text → failure
        retriever = _make_retriever(
            side_effects=[
                _mock_response(500),                   # bolls first
                _mock_response(500),                   # bolls retry
                _mock_response(200, api_bible_data),   # api.bible: 200 but empty content
            ],
            api_bible_key="test-key",
        )
        result = retriever.retrieve("Romans 8:15", "NASB", operator_import=csv_path)
        assert isinstance(result, ScriptureFailureAlert)
        assert result.attempted_sources == ["bolls_life", "api_bible", "operator_import"]

    def test_unparseable_reference_returns_alert_immediately(self):
        """Malformed reference → FailureMode.UNPARSEABLE_REFERENCE; no sources attempted."""
        retriever = ScriptureRetriever()
        result = retriever.retrieve("not a scripture reference at all")
        assert isinstance(result, ScriptureFailureAlert)
        assert result.failure_mode == FailureMode.UNPARSEABLE_REFERENCE
        assert result.attempted_sources == []


# ---------------------------------------------------------------------------
# TestOperatorImport
# ---------------------------------------------------------------------------


class TestOperatorImport:
    def test_lookup_is_case_insensitive(self, tmp_path):
        """CSV reference and translation in different case still matches."""
        csv_path = _make_csv(
            [{"reference": "romans 8:15", "translation": "nasb", "text": "Case test text"}],
            tmp_path,
        )
        retriever = _make_retriever([
            _mock_response(500),
            _mock_response(500),
        ])
        result = retriever.retrieve("Romans 8:15", "NASB", operator_import=csv_path)
        assert isinstance(result, ScriptureResult)
        assert result.text == "Case test text"
        assert result.verification_status == "operator_imported"

    def test_missing_reference_in_csv_falls_to_failure(self, tmp_path):
        """CSV doesn't contain the requested verse → ScriptureFailureAlert."""
        csv_path = _make_csv(
            [{"reference": "John 3:16", "translation": "NASB", "text": "For God so loved"}],
            tmp_path,
        )
        retriever = _make_retriever([
            _mock_response(500),
            _mock_response(500),
        ])
        result = retriever.retrieve("Romans 8:15", "NASB", operator_import=csv_path)
        assert isinstance(result, ScriptureFailureAlert)

    def test_bolls_success_bypasses_operator_import(self, tmp_path):
        """Bolls.life succeeds → operator import is never consulted."""
        csv_path = _make_csv(
            [{"reference": "Romans 8:15", "translation": "NASB", "text": "CSV text"}],
            tmp_path,
        )
        verse_data = _bolls_verse(45, 8, 15, "Bolls life text")
        retriever = _make_retriever([_mock_response(200, [verse_data])])
        result = retriever.retrieve("Romans 8:15", "NASB", operator_import=csv_path)
        assert isinstance(result, ScriptureResult)
        assert result.retrieval_source == "bolls_life"
        assert result.text == "Bolls life text"
