"""semantic_exposition_rag.py — Phase 014 CP5 SemanticExpositionRAG.

Implements ExpositionRAGInterface using TF-IDF VectorRetrievalEngine.

Design guarantees (inherited from VectorRetrievalEngine):
- FAIL FAST: raises FileNotFoundError at __init__ if index or corpus is missing.
- NO AUTO-BUILD: never builds or writes the index. [AC-1]
- ZERO DISK WRITES: retrieve_for_paragraph() performs no disk I/O. [AC-1]
- DETERMINISTIC: same inputs → identical ordered results.
- OFFLINE SAFE: no network calls, no model downloads.

Source identity [AC-3]:
    Every RetrievedExcerpt.source_title produced via format_source_title()
    exclusively — enforced inside VectorRetrievalEngine.retrieve().

Shortage protocol:
    Returns [] when no candidates meet the configured threshold or when
    the query has no vocabulary overlap with the index.

NOT wired into generation_pipeline.py. This module is implementation-only.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from src.interfaces.rag import ExpositionRAGInterface, RetrievedExcerpt
from src.rag.retrieval_engine import VectorRetrievalEngine

# ---------------------------------------------------------------------------
# Canonical default paths (same anchoring convention as retrieval_engine.py)
# ---------------------------------------------------------------------------

_DEFAULT_INDEX_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "index" / "excerpts-index.json"
)
_DEFAULT_CORPUS_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "corpus" / "excerpts-corpus.json"
)


class SemanticExpositionRAG:
    """Exposition RAG backed by TF-IDF VectorRetrievalEngine.

    Implements the ExpositionRAGInterface protocol. Delegates all retrieval
    to VectorRetrievalEngine, which provides deterministic cosine-similarity
    scoring over the committed index artifact.

    Args:
        index_path:  Path to the pre-built TF-IDF index JSON. Must exist.
        corpus_path: Path to the excerpts corpus JSON. Must exist.
        top_k:       Maximum results per retrieve_for_paragraph() call (default 5).
        threshold:   Minimum cosine similarity to include a result (default 0.0).

    Raises:
        FileNotFoundError: at construction if index_path or corpus_path is absent.
    """

    def __init__(
        self,
        index_path: Path = _DEFAULT_INDEX_PATH,
        corpus_path: Path = _DEFAULT_CORPUS_PATH,
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> None:
        # Fail fast: VectorRetrievalEngine raises FileNotFoundError at __init__
        # if either file is missing. No auto-build. [AC-1]
        self._engine = VectorRetrievalEngine(
            index_path=Path(index_path),
            corpus_path=Path(corpus_path),
        )
        self._top_k = top_k
        self._threshold = threshold

    def retrieve_for_paragraph(
        self,
        paragraph_type: str,
        passage_reference: str,
        topic: str,
        source_types: List[str],
    ) -> List[RetrievedExcerpt]:
        """Retrieve excerpts for a paragraph slot via TF-IDF cosine similarity.

        Delegates to VectorRetrievalEngine.retrieve(). All source_title values
        in returned excerpts are produced via format_source_title() [AC-3].
        Performs ZERO DISK WRITES. [AC-1]

        Args:
            paragraph_type:    "context" | "theological"
            passage_reference: Scripture reference (e.g. "Lamentations 3:22").
            topic:             Devotional theme (e.g. "compassion").
            source_types:      Accepted source_type values (e.g. ["commentary"]).

        Returns:
            List[RetrievedExcerpt] sorted by score DESC, source_id ASC for ties.
            Returns [] if no matches meet the threshold or query is empty/OOV.
        """
        return self._engine.retrieve(
            paragraph_type=paragraph_type,
            source_types=source_types,
            passage_reference=passage_reference,
            topic=topic,
            top_k=self._top_k,
            threshold=self._threshold,
        )
