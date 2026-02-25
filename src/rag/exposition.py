"""exposition.py — Phase 005 CP2 ExpositionRAG: concrete ExpositionRAGInterface implementation.

Loads excerpt data from a JSON seed file at construction time. Retrieval is
deterministic: filter by paragraph_type + source_types, with a source_types-only
fallback if no paragraph_type matches. Insertion-order within filtered set.
No LLM calls. No network calls. No embeddings.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.interfaces.rag import RetrievedExcerpt

_DEFAULT_EXCERPTS_PATH = (
    Path(__file__).parent.parent.parent / "data" / "excerpts" / "seed-excerpts.json"
)


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
        with excerpts_path.open(encoding="utf-8") as fh:
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

        primary = [
            e for e in self._raw
            if e["paragraph_type"] == paragraph_type and e["source_type"] in source_types
        ]
        matched = primary if primary else [
            e for e in self._raw if e["source_type"] in source_types
        ]

        return [
            RetrievedExcerpt(
                text=e["text"],
                source_title=e["source_title"],
                author=e["author"],
                source_type=e["source_type"],
            )
            for e in matched
        ]
