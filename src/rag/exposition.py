"""exposition.py — Phase 005 CP2 ExpositionRAG: concrete ExpositionRAGInterface implementation.

Loads excerpt data from a JSON seed file at construction time. Retrieval is
deterministic: filter by paragraph_type + source_types, with a source_types-only
fallback if no paragraph_type matches. Insertion-order within filtered set.
No LLM calls. No network calls. No embeddings.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List
import re

from src.interfaces.rag import RetrievedExcerpt
from src.persistence.paths import default_registry_db_path
from src.rag.sqlite_catalog import load_excerpt_rows
from src.validation.modernization import modernization_payload

_DEFAULT_EXCERPTS_PATH = (
    Path(__file__).parent.parent.parent / "data" / "excerpts" / "seed-excerpts.json"
)

_BOOK_PATTERNS: dict[str, re.Pattern[str]] = {
    name: re.compile(rf"\b{re.escape(name.lower())}\b")
    for name in [
        "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges",
        "Ruth", "Samuel", "Kings", "Chronicles", "Ezra", "Nehemiah", "Esther", "Job",
        "Psalm", "Psalms", "Proverbs", "Ecclesiastes", "Song", "Isaiah", "Jeremiah",
        "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah",
        "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi",
        "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "Corinthians", "Galatians",
        "Ephesians", "Philippians", "Colossians", "Thessalonians", "Timothy", "Titus",
        "Philemon", "Hebrews", "James", "Peter", "Jude", "Revelation",
    ]
}


def _target_books(reference: str) -> set[str]:
    ref = str(reference or "").lower()
    matched = {name for name, pattern in _BOOK_PATTERNS.items() if pattern.search(ref)}
    if "psalm" in matched:
        matched.add("Psalms")
    if "psalms" in matched:
        matched.add("Psalm")
    return matched


def _mentioned_books(*parts: str) -> set[str]:
    haystack = " ".join(str(part or "").lower() for part in parts)
    return {name for name, pattern in _BOOK_PATTERNS.items() if pattern.search(haystack)}


class ExpositionRAG:
    """Concrete implementation of ExpositionRAGInterface backed by a JSON seed file.

    The seed file entries must include all RetrievedExcerpt fields plus
    a "paragraph_type" key used for filtering (not exposed in the return type).

    Filter logic:
        Primary:  paragraph_type == requested AND source_type in source_types
        Fallback: source_type in source_types (when primary yields no results)

    Returns [] only when source_types is empty or no seed entry matches any
    value in source_types.

    Deterministic: results are returned in seed-file insertion order within
    each filtered set; no sorting or randomisation applied.
    """

    def __init__(self, excerpts_path: Path = _DEFAULT_EXCERPTS_PATH) -> None:
        resolved = Path(excerpts_path).resolve()
        if resolved == _DEFAULT_EXCERPTS_PATH.resolve():
            db_path = default_registry_db_path()
            strict_db_only = os.getenv("DEVG_REQUIRE_DB_CATALOG", "").strip() == "1"
            self._raw = load_excerpt_rows(
                db_path=db_path,
                seed_path=resolved,
                strict_db_only=strict_db_only,
            )
        else:
            with resolved.open(encoding="utf-8") as fh:
                self._raw: List[Dict[str, Any]] = json.load(fh)

    def retrieve_for_paragraph(
        self,
        paragraph_type: str,
        passage_reference: str,
        topic: str,
        source_types: List[str],
    ) -> List[RetrievedExcerpt]:
        """Return excerpts matching paragraph_type and source_types.

        Args:
            paragraph_type: "context" or "theological".
            passage_reference: Scripture passage (ignored by seed implementation;
                included for interface compatibility).
            topic: Devotional theme (ignored by seed implementation;
                included for interface compatibility).
            source_types: List of accepted source_type values (e.g. ["commentary"]).

        Returns:
            List[RetrievedExcerpt] in seed-file insertion order.
            Falls back to source_types-only match if no paragraph_type match.
            Returns [] if source_types is empty or catalog has no matching entries.
        """
        if not source_types:
            return []

        target_books = _target_books(passage_reference)
        query_tokens = {
            token
            for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", f"{passage_reference} {topic}".lower())
            if token not in {"and", "the", "with", "day", "matthew", "mark", "luke", "john", "romans", "genesis"}
        }
        # Normalise the query passage reference for direct matching.
        norm_ref = " ".join(str(passage_reference or "").lower().split())

        def _entry_allowed(entry: Dict[str, Any]) -> bool:
            # Prefer passage_reference direct match when the field is populated
            # (set during indexing).  Fall back to book-mention heuristic for
            # seed entries that predate the indexed field.
            entry_ref = str(entry.get("passage_reference", "")).strip().lower()
            if entry_ref:
                # Direct match: the indexed entry was tagged to this passage.
                return norm_ref in entry_ref or entry_ref in norm_ref
            # Heuristic fallback: check whether the excerpt text mentions the
            # target book (used for un-indexed seed entries).
            mentioned_books = _mentioned_books(entry.get("text", ""))
            if target_books and mentioned_books and target_books.isdisjoint(mentioned_books):
                return False
            return True

        primary_matches = [
            entry
            for entry in self._raw
            if entry["paragraph_type"] == paragraph_type
            and entry["source_type"] in source_types
            and _entry_allowed(entry)
        ]

        scored: list[tuple[int, Dict[str, Any]]] = []
        for entry in primary_matches:
            haystack = f"{entry.get('text', '')} {entry.get('source_title', '')} {entry.get('author', '')}".lower()
            overlap = len({token for token in query_tokens if token in haystack})
            if overlap > 0:
                scored.append((overlap, entry))

        if scored:
            matched = [entry for _, entry in sorted(scored, key=lambda item: (-item[0], self._raw.index(item[1])))]
        elif primary_matches:
            matched = primary_matches
        else:
            matched = [
                entry
                for entry in self._raw
                if entry["source_type"] in source_types and _entry_allowed(entry)
            ]

        return [
            RetrievedExcerpt(
                text=display_text,
                original_text=original_text,
                language_modernized=language_modernized,
                modernization_label=modernization_label,
                source_title=e["source_title"],
                author=e["author"],
                source_type=e["source_type"],
                relevance_score=float(next((score for score, entry in scored if entry is e), 1.0)),
            )
            for e in matched
            for display_text, original_text, language_modernized, modernization_label
            in [modernization_payload(e["text"])]
        ]
