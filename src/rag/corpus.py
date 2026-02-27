"""corpus.py — Corpus schema, loader, and source_title formatter.

Defines the canonical CorpusDocument dataclass, corpus loading/validation,
and the single source_title formatting contract enforced across all Phase 014
retrieval code.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Source-title contract [AC-3]
# ---------------------------------------------------------------------------

_SOURCE_TITLE_DELIMITER = " | "
_VALID_SOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*[a-z0-9]$")


def format_source_title(source_id: str, canonical_citation: str) -> str:
    """Format source_title for RetrievedExcerpt. Single canonical form.

    Returns: "<source_id> | <canonical_citation>"
    Delimiter is exactly ' | ' (space-pipe-space). No variants permitted.
    """
    return f"{source_id}{_SOURCE_TITLE_DELIMITER}{canonical_citation}"


def parse_source_id(source_title: str) -> str:
    """Extract source_id from a formatted source_title.

    Raises:
        ValueError: if source_title does not contain exactly one ' | ' delimiter.
    """
    parts = source_title.split(_SOURCE_TITLE_DELIMITER, maxsplit=1)
    if len(parts) != 2:
        raise ValueError(
            f"source_title does not match '<source_id> | <citation>' format: {source_title!r}"
        )
    return parts[0]


# ---------------------------------------------------------------------------
# Corpus document schema
# ---------------------------------------------------------------------------

@dataclass
class CorpusDocument:
    """One document in the corpus following the Section B-1 canonical schema."""

    source_id: str
    author: str
    work: str
    publication_year: Optional[int]
    canonical_citation: str
    text: str
    source_type: str    # "commentary" | "reference"
    paragraph_type: str  # "context" | "theological"

    @property
    def source_title(self) -> str:
        """Canonical source_title string for use in RetrievedExcerpt."""
        return format_source_title(self.source_id, self.canonical_citation)


# ---------------------------------------------------------------------------
# Corpus loader
# ---------------------------------------------------------------------------

_VALID_SOURCE_TYPES = {"commentary", "reference"}
_VALID_PARAGRAPH_TYPES = {"context", "theological"}


def load_corpus(path: Path) -> List[CorpusDocument]:
    """Load and validate a corpus JSON file.

    Expected structure:
        {
          "provenance": { ... },
          "documents": [ { <CorpusDocument fields> }, ... ]
        }

    Raises:
        FileNotFoundError: if path does not exist.
        ValueError: if JSON structure or any document fails schema validation.
    """
    if not path.exists():
        raise FileNotFoundError(f"Corpus file not found: {path}")

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"Corpus JSON must be an object, got {type(data).__name__}")
    if "documents" not in data:
        raise ValueError("Corpus JSON missing 'documents' key")
    if not isinstance(data["documents"], list):
        raise ValueError("Corpus 'documents' must be a list")

    docs: List[CorpusDocument] = []
    for idx, raw in enumerate(data["documents"]):
        try:
            doc = _parse_document(raw, idx)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid corpus document at index {idx}: {exc}") from exc
        docs.append(doc)

    validate_corpus(docs)
    return docs


def _parse_document(raw: dict, idx: int) -> CorpusDocument:
    """Parse and lightly type-check one raw document dict."""
    required = ("source_id", "author", "work", "canonical_citation", "text", "source_type", "paragraph_type")
    for key in required:
        if key not in raw:
            raise ValueError(f"Missing required field '{key}' in document {idx}")

    publication_year = raw.get("publication_year")
    if publication_year is not None and not isinstance(publication_year, int):
        raise ValueError(f"'publication_year' must be int or null, got {type(publication_year).__name__}")

    return CorpusDocument(
        source_id=str(raw["source_id"]),
        author=str(raw["author"]),
        work=str(raw["work"]),
        publication_year=publication_year,
        canonical_citation=str(raw["canonical_citation"]),
        text=str(raw["text"]),
        source_type=str(raw["source_type"]),
        paragraph_type=str(raw["paragraph_type"]),
    )


def validate_corpus(docs: List[CorpusDocument]) -> None:
    """Validate a list of CorpusDocuments for schema compliance and internal consistency.

    Raises:
        ValueError: on any violation.
    """
    if not docs:
        raise ValueError("Corpus must contain at least one document")

    seen_ids: set[str] = set()
    for doc in docs:
        # source_id: non-empty slug (lowercase, alphanumeric, underscore; starts/ends with alnum)
        if not doc.source_id:
            raise ValueError("source_id must not be empty")
        if not _VALID_SOURCE_ID_RE.match(doc.source_id):
            raise ValueError(
                f"source_id {doc.source_id!r} is not a valid slug "
                f"(must match ^[a-z][a-z0-9_]*[a-z0-9]$)"
            )
        if doc.source_id in seen_ids:
            raise ValueError(f"Duplicate source_id: {doc.source_id!r}")
        seen_ids.add(doc.source_id)

        # canonical_citation: required non-empty
        if not doc.canonical_citation.strip():
            raise ValueError(f"canonical_citation must not be empty for source_id={doc.source_id!r}")

        # text: required non-empty
        if not doc.text.strip():
            raise ValueError(f"text must not be empty for source_id={doc.source_id!r}")

        # source_type enum
        if doc.source_type not in _VALID_SOURCE_TYPES:
            raise ValueError(
                f"source_type {doc.source_type!r} not in {_VALID_SOURCE_TYPES} "
                f"for source_id={doc.source_id!r}"
            )

        # paragraph_type enum
        if doc.paragraph_type not in _VALID_PARAGRAPH_TYPES:
            raise ValueError(
                f"paragraph_type {doc.paragraph_type!r} not in {_VALID_PARAGRAPH_TYPES} "
                f"for source_id={doc.source_id!r}"
            )
