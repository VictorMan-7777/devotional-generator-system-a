"""retrieval_engine.py — Deterministic TF-IDF vector retrieval engine.

Design guarantees:
- FAIL FAST: raises FileNotFoundError at __init__ if index or corpus is missing.
- NO AUTO-BUILD: never builds or writes the index. [AC-1]
- ZERO DISK WRITES: retrieve() performs no disk I/O of any kind. [AC-1]
- DETERMINISTIC: same inputs → identical ordered results.
- OFFLINE SAFE: no network calls, no model downloads.
"""
from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

from src.interfaces.rag import RetrievedExcerpt
from src.rag.corpus import CorpusDocument, format_source_title, load_corpus
from src.rag.index_builder import CorpusIndexBuilder, _tokenize

_DEFAULT_INDEX_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "index" / "excerpts-index.json"
)
_DEFAULT_CORPUS_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "corpus" / "excerpts-corpus.json"
)


# ---------------------------------------------------------------------------
# Sparse vector math helpers
# ---------------------------------------------------------------------------

def _l2_norm(vec: Dict[str, float]) -> float:
    """Compute L2 norm of a sparse vector."""
    return math.sqrt(sum(v * v for v in vec.values()))


def _cosine_similarity(
    query_vec: Dict[str, float],
    query_norm: float,
    doc_tfidf: Dict[str, float],
) -> float:
    """Cosine similarity between a query vector and a document TF-IDF vector.

    Returns 0.0 when there is no vocabulary overlap or either vector is zero.
    Both vectors have non-negative components so the result is in [0.0, 1.0].
    """
    dot = sum(query_vec[t] * doc_tfidf[t] for t in query_vec if t in doc_tfidf)
    if dot == 0.0:
        return 0.0
    doc_norm = _l2_norm(doc_tfidf)
    if doc_norm == 0.0:
        return 0.0
    return dot / (query_norm * doc_norm)


# ---------------------------------------------------------------------------
# VectorRetrievalEngine
# ---------------------------------------------------------------------------

class VectorRetrievalEngine:
    """TF-IDF vector retrieval engine backed by a pre-built index.

    Loads index and corpus at construction time (fail-fast). All subsequent
    retrieve() calls operate entirely in memory — zero disk I/O.
    """

    def __init__(
        self,
        index_path: Path = _DEFAULT_INDEX_PATH,
        corpus_path: Path = _DEFAULT_CORPUS_PATH,
    ) -> None:
        """Load index and corpus. Fail immediately if either file is absent.

        Raises:
            FileNotFoundError: if index_path or corpus_path does not exist.
            ValueError: if the index JSON is missing required keys.
        """
        index_path = Path(index_path)
        corpus_path = Path(corpus_path)

        # FAIL FAST before doing anything else [AC-1]
        if not index_path.exists():
            raise FileNotFoundError(
                f"Index file not found (run scripts/rag/build-index.py to build): "
                f"{index_path}"
            )
        if not corpus_path.exists():
            raise FileNotFoundError(f"Corpus file not found: {corpus_path}")

        # Load and validate index (raises ValueError on schema violations)
        builder = CorpusIndexBuilder()
        self._index = builder.load(index_path)

        # Prepare in-memory lookup structures
        self._vocab_set: set[str] = set(self._index["vocabulary"])
        self._idf: Dict[str, float] = self._index["idf"]
        self._doc_entries: List[dict] = self._index["documents"]

        # Load corpus for full text and author (not stored in index)
        corpus_docs = load_corpus(corpus_path)
        self._doc_lookup: Dict[str, CorpusDocument] = {
            d.source_id: d for d in corpus_docs
        }

    # -----------------------------------------------------------------------
    # Retrieval — zero disk I/O after construction
    # -----------------------------------------------------------------------

    def retrieve(
        self,
        paragraph_type: str,
        source_types: List[str],
        passage_reference: str,
        topic: str,
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> List[RetrievedExcerpt]:
        """Retrieve top-K documents by TF-IDF cosine similarity.

        Determinism:
            Primary sort: cosine similarity score DESC.
            Tie-break:    source_id ASC (string sort).

        Shortage protocol:
            Returns [] when no candidates meet the threshold or the query
            has no vocabulary overlap with the index.

        Source identity [AC-3]:
            Every returned RetrievedExcerpt.source_title is produced
            exclusively via format_source_title(source_id, canonical_citation).

        Performs ZERO DISK WRITES. [AC-1]

        Args:
            paragraph_type: "context" | "theological"
            source_types:   Accepted source_type values (e.g. ["commentary"]).
            passage_reference: Scripture reference (e.g. "Lamentations 3:22").
            topic:          Devotional theme (e.g. "compassion").
            top_k:          Maximum number of results to return.
            threshold:      Minimum cosine similarity score (default 0.0).

        Returns:
            List[RetrievedExcerpt] sorted by score DESC, source_id ASC for ties.
            Returns [] if no matches or empty query.
        """
        if not source_types:
            return []

        # Build deterministic query from passage reference + topic
        query_text = f"{passage_reference} {topic}"
        query_vec = self._vectorize_query(query_text)
        if not query_vec:
            return []
        query_norm = _l2_norm(query_vec)
        if query_norm == 0.0:
            return []

        # Filter and score candidates
        scored: List[Tuple[float, str, dict]] = []
        for entry in self._doc_entries:
            if entry["paragraph_type"] != paragraph_type:
                continue
            if entry["source_type"] not in source_types:
                continue

            score = _cosine_similarity(query_vec, query_norm, entry["tfidf"])
            if score >= threshold:
                scored.append((score, entry["source_id"], entry))

        # Sort: score DESC, source_id ASC for deterministic tie-breaking
        scored.sort(key=lambda x: (-x[0], x[1]))

        # Take top_k and build RetrievedExcerpt results
        results: List[RetrievedExcerpt] = []
        for score, source_id, _entry in scored[:top_k]:
            doc = self._doc_lookup.get(source_id)
            if doc is None:
                # Should not happen if index and corpus are in sync
                continue
            results.append(
                RetrievedExcerpt(
                    text=doc.text,
                    source_title=format_source_title(  # [AC-3]
                        source_id, doc.canonical_citation
                    ),
                    author=doc.author,
                    source_type=doc.source_type,
                    relevance_score=score,
                )
            )

        return results

    # -----------------------------------------------------------------------
    # Internal: query vectorization (in-memory only)
    # -----------------------------------------------------------------------

    def _vectorize_query(self, text: str) -> Dict[str, float]:
        """Build a TF-IDF query vector using corpus IDF weights.

        Uses the same tokenizer as the index builder to ensure alignment.
        Only vocabulary terms present in the index contribute to the vector.
        Returns {} for empty or fully-OOV queries.
        """
        tokens = _tokenize(text)
        if not tokens:
            return {}

        tf_counts = Counter(tokens)
        doc_len = len(tokens)

        return {
            t: round((count / doc_len) * self._idf[t], 10)
            for t, count in tf_counts.items()
            if t in self._vocab_set
        }
