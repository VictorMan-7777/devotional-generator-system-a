"""
Scripture retrieval module — FR-57 through FR-60.

Priority chain (FR-59):
  1. Bolls.life API — primary source, one retry on failure (FR-59a)
  2. API.Bible    — secondary, only when api_bible_key is supplied (FR-59b)
  3. Operator import file — CSV fallback (FR-59c)
  4. ScriptureFailureAlert — structured failure object; caller surfaces to operator (FR-59d–f)

Validation (FR-58):
  - verse field in Bolls.life response matches the requested verse number
  - text field is non-empty after HTML tag stripping
  - book and chapter are implicitly validated by URL construction (baked into request URL);
    they are augmented onto the response dict before validate_match for uniform interface.

Network isolation:
  All HTTP calls are routed through HttpClient, which is injected at construction
  time. Tests pass a mock; production uses httpx.Client.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel

from src.scripture.book_ids import BOOK_IDS, get_book_id

# ---------------------------------------------------------------------------
# Bolls.life → API.Bible passage-ID abbreviation table (NT + frequently used OT)
# ---------------------------------------------------------------------------

_API_BIBLE_ABBR: dict[int, str] = {
    1: "GEN",  2: "EXO",  3: "LEV",  4: "NUM",  5: "DEU",
    6: "JOS",  7: "JDG",  8: "RUT",  9: "1SA",  10: "2SA",
    11: "1KI", 12: "2KI", 13: "1CH", 14: "2CH", 15: "EZR",
    16: "NEH", 17: "EST", 18: "JOB", 19: "PSA", 20: "PRO",
    21: "ECC", 22: "SNG", 23: "ISA", 24: "JER", 25: "LAM",
    26: "EZK", 27: "DAN", 28: "HOS", 29: "JOL", 30: "AMO",
    31: "OBA", 32: "JON", 33: "MIC", 34: "NAM", 35: "HAB",
    36: "ZEP", 37: "HAG", 38: "ZEC", 39: "MAL",
    40: "MAT", 41: "MRK", 42: "LUK", 43: "JHN", 44: "ACT",
    45: "ROM", 46: "1CO", 47: "2CO", 48: "GAL", 49: "EPH",
    50: "PHP", 51: "COL", 52: "1TH", 53: "2TH", 54: "1TI",
    55: "2TI", 56: "TIT", 57: "PHM", 58: "HEB", 59: "JAS",
    60: "1PE", 61: "2PE", 62: "1JN", 63: "2JN", 64: "3JN",
    65: "JUD", 66: "REV",
}

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ParsedReference:
    book_name: str
    book_id: int
    chapter: int
    verses: list[int]  # e.g. [15] or [15, 16, 17]


class FailureMode(str, Enum):
    UNPARSEABLE_REFERENCE = "unparseable_reference"
    PRIMARY_EXHAUSTED = "primary_exhausted"        # Bolls.life both attempts failed
    ALL_SOURCES_EXHAUSTED = "all_sources_exhausted"  # Nothing worked
    VALIDATION_FAILURE = "validation_failure"


class ScriptureResult(BaseModel):
    reference: str
    text: str  # HTML-stripped; multi-verse concatenated with single space
    translation: str
    retrieval_source: str   # "bolls_life" | "api_bible" | "operator_import"
    verification_status: str = "verified"


class ScriptureFailureAlert(BaseModel):
    reference: str
    translation: str
    failure_mode: FailureMode
    message: str
    attempted_sources: list[str]


# ---------------------------------------------------------------------------
# HTTP client wrapper — inject a mock to avoid network calls in tests
# ---------------------------------------------------------------------------


class HttpClient:
    """Thin wrapper around httpx.Client.  Inject a MagicMock in tests."""

    def __init__(self, client: Optional[httpx.Client] = None) -> None:
        self._client = client or httpx.Client(timeout=10.0)

    def get(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        return self._client.get(url, headers=headers or {})

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# ScriptureRetriever
# ---------------------------------------------------------------------------


class ScriptureRetriever:
    """
    Retrieves scripture via a prioritised fallback chain (FR-59).

    Inject `http_client` to isolate network calls in tests.
    Inject `api_bible_key` to enable the API.Bible secondary source.
    """

    BOLLS_LIFE_BASE = "https://bolls.life/get-verse"
    API_BIBLE_BASE = "https://api.scripture.api.bible/v1"
    # Default API.Bible bible ID for NASB; override via constructor if needed.
    DEFAULT_API_BIBLE_BIBLE_ID = "72c7f6f5e7fa1b62-01"

    def __init__(
        self,
        http_client: Optional[HttpClient] = None,
        api_bible_key: Optional[str] = None,
        api_bible_bible_id: Optional[str] = None,
    ) -> None:
        self._http = http_client or HttpClient()
        self._api_bible_key = api_bible_key
        self._api_bible_bible_id = api_bible_bible_id or self.DEFAULT_API_BIBLE_BIBLE_ID

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve(
        self,
        reference: str,
        translation: str = "NASB",
        operator_import: Optional[Path] = None,
    ) -> ScriptureResult | ScriptureFailureAlert:
        """
        Return a ScriptureResult on success or a ScriptureFailureAlert on
        complete failure, following the priority chain defined in FR-59.
        """
        try:
            parsed = self._parse_reference(reference)
        except ValueError as exc:
            return ScriptureFailureAlert(
                reference=reference,
                translation=translation,
                failure_mode=FailureMode.UNPARSEABLE_REFERENCE,
                message=str(exc),
                attempted_sources=[],
            )

        attempted: list[str] = []

        # 1. Bolls.life primary — one retry on failure (FR-59a)
        result = self._try_bolls_life(parsed, translation)
        if isinstance(result, ScriptureResult):
            return result
        attempted.append("bolls_life")

        # 2. API.Bible secondary — only when key is present (FR-59b)
        if self._api_bible_key:
            result = self._try_api_bible(reference, translation)
            if isinstance(result, ScriptureResult):
                return result
            attempted.append("api_bible")

        # 3. Operator import file (FR-59c)
        if operator_import is not None:
            result = self._load_operator_import(reference, translation, operator_import)
            if isinstance(result, ScriptureResult):
                return result
            attempted.append("operator_import")

        # 4. Structured failure alert (FR-59d–f)
        return ScriptureFailureAlert(
            reference=reference,
            translation=translation,
            failure_mode=FailureMode.ALL_SOURCES_EXHAUSTED,
            message=(
                f"All retrieval sources exhausted for '{reference}' ({translation}). "
                "Manual entry required."
            ),
            attempted_sources=attempted,
        )

    def validate_match(
        self,
        response: dict,
        reference: str,
        translation: str,
    ) -> bool:
        """
        FR-58 validation: confirm a Bolls.life verse response matches the
        requested reference.

        Checks:
          - response["book"]    == parsed book_id
          - response["chapter"] == parsed chapter
          - response["verse"]   is in the expected verse list
          - response["text"] is non-empty after HTML tag stripping
        """
        try:
            parsed = self._parse_reference(reference)
        except ValueError:
            return False

        book_ok = response.get("book") == parsed.book_id
        chapter_ok = response.get("chapter") == parsed.chapter
        verse_ok = response.get("verse") in parsed.verses
        stripped = self._strip_html(response.get("text", "")).strip()
        text_ok = bool(stripped)

        return book_ok and chapter_ok and verse_ok and text_ok

    # ------------------------------------------------------------------
    # Bolls.life
    # ------------------------------------------------------------------

    def _try_bolls_life(
        self,
        parsed: ParsedReference,
        translation: str,
    ) -> Optional[ScriptureResult]:
        """Attempt Bolls.life with exactly one retry on failure (FR-59a)."""
        for _ in range(2):  # first attempt + one retry
            try:
                result = self._fetch_bolls_life(parsed, translation)
                if isinstance(result, ScriptureResult):
                    return result
            except Exception:
                pass
        return None

    def _fetch_bolls_life(
        self,
        parsed: ParsedReference,
        translation: str,
    ) -> Optional[ScriptureResult]:
        """
        Fetch all requested verses from Bolls.life and return a ScriptureResult
        if every verse passes FR-58 validation. Returns None on any failure.
        """
        verse_texts: list[str] = []

        for verse_num in parsed.verses:
            url = (
                f"{self.BOLLS_LIFE_BASE}/{translation}/"
                f"{parsed.book_id}/{parsed.chapter}/{verse_num}/"
            )
            response = self._http.get(url)

            if response.status_code != 200:
                return None

            data = response.json()
            if not data or not isinstance(data, dict):
                return None

            # Augment with book and chapter (not returned by API; derived from URL).
            # This keeps validate_match interface uniform across sources.
            verse_data = {**data, "book": parsed.book_id, "chapter": parsed.chapter}

            # Per-verse FR-58 validation
            verse_ref = f"{parsed.book_name} {parsed.chapter}:{verse_num}"
            if not self.validate_match(verse_data, verse_ref, translation):
                return None

            verse_texts.append(self._strip_html(verse_data["text"]))

        combined = " ".join(verse_texts).strip()
        if not combined:
            return None

        ref_str = f"{parsed.book_name} {parsed.chapter}:{parsed.verses[0]}"
        if len(parsed.verses) > 1:
            ref_str += f"-{parsed.verses[-1]}"

        return ScriptureResult(
            reference=ref_str,
            text=combined,
            translation=translation,
            retrieval_source="bolls_life",
            verification_status="verified",
        )

    # ------------------------------------------------------------------
    # API.Bible  (FR-59b)
    # ------------------------------------------------------------------

    def _try_api_bible(
        self,
        reference: str,
        translation: str,
    ) -> Optional[ScriptureResult]:
        """Attempt API.Bible retrieval. Returns None on any failure."""
        if not self._api_bible_key:
            return None
        try:
            passage_id = self._to_api_bible_passage_id(reference)
            url = (
                f"{self.API_BIBLE_BASE}/bibles/{self._api_bible_bible_id}"
                f"/passages/{passage_id}"
                f"?content-type=text&include-verse-numbers=false"
            )
            response = self._http.get(url, headers={"api-key": self._api_bible_key})

            if response.status_code != 200:
                return None

            data = response.json()
            text = self._strip_html(
                data.get("data", {}).get("content", "")
            ).strip()
            if not text:
                return None

            return ScriptureResult(
                reference=reference,
                text=text,
                translation=translation,
                retrieval_source="api_bible",
                verification_status="verified",
            )
        except Exception:
            return None

    def _to_api_bible_passage_id(self, reference: str) -> str:
        """
        Convert 'Romans 8:15' → 'ROM.8.15' (API.Bible passage ID format).
        Multi-verse 'Romans 8:15-17' → 'ROM.8.15-ROM.8.17'.
        """
        parsed = self._parse_reference(reference)
        abbr = _API_BIBLE_ABBR.get(parsed.book_id, f"B{parsed.book_id:02d}")
        start = f"{abbr}.{parsed.chapter}.{parsed.verses[0]}"
        if len(parsed.verses) == 1:
            return start
        end = f"{abbr}.{parsed.chapter}.{parsed.verses[-1]}"
        return f"{start}-{end}"

    # ------------------------------------------------------------------
    # Operator import file  (FR-59c)
    # ------------------------------------------------------------------

    def _load_operator_import(
        self,
        reference: str,
        translation: str,
        path: Path,
    ) -> Optional[ScriptureResult]:
        """
        Load scripture from an operator-provided CSV file.

        Expected CSV columns: reference, translation, text
        Lookup is case-insensitive on reference and translation.
        """
        try:
            with path.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    row_ref = row.get("reference", "").strip()
                    row_trans = row.get("translation", "").strip().upper()
                    if (
                        row_ref.lower() == reference.lower()
                        and row_trans == translation.upper()
                    ):
                        text = row.get("text", "").strip()
                        if text:
                            return ScriptureResult(
                                reference=reference,
                                text=text,
                                translation=translation,
                                retrieval_source="operator_import",
                                verification_status="operator_imported",
                            )
        except (OSError, KeyError, csv.Error):
            return None
        return None

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_reference(reference: str) -> ParsedReference:
        """
        Parse 'Romans 8:15' or '1 Corinthians 13:4-7' into a ParsedReference.

        Raises ValueError for unrecognised formats or unknown book names.
        """
        pattern = r"^(.+?)\s+(\d+):(\d+)(?:-(\d+))?$"
        match = re.match(pattern, reference.strip())
        if not match:
            raise ValueError(
                f"Cannot parse scripture reference: '{reference}'. "
                "Expected format: 'Book Chapter:Verse' or 'Book Chapter:Start-End'."
            )

        book_name = match.group(1).strip()
        chapter = int(match.group(2))
        verse_start = int(match.group(3))
        verse_end = int(match.group(4)) if match.group(4) else verse_start

        book_id = get_book_id(book_name)
        if book_id is None:
            raise ValueError(
                f"Unknown book name: '{book_name}'. "
                "Check spelling or add abbreviation to book_ids.py."
            )

        return ParsedReference(
            book_name=book_name,
            book_id=book_id,
            chapter=chapter,
            verses=list(range(verse_start, verse_end + 1)),
        )

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags from text (FR-58)."""
        return re.sub(r"<[^>]+>", "", text)
