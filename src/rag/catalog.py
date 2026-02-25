"""catalog.py — Phase 005 CP1 QuoteCatalog: concrete QuoteRAGInterface implementation.

Loads quote data from a JSON seed file at construction time. Retrieval is
deterministic: keyword-overlap scoring, then alphabetical tie-breaking.
No LLM calls. No network calls. No embeddings.

Shortage protocol: if the result set has < 3 candidates, emits a structured
warnings.warn() message and returns all available candidates without raising.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Dict, List, Optional

from src.interfaces.rag import QuoteCandidate

_DEFAULT_CATALOG_PATH = (
    Path(__file__).parent.parent.parent / "data" / "quotes" / "seed-quotes.json"
)


class QuoteCatalog:
    """Concrete implementation of QuoteRAGInterface backed by a JSON seed file.

    Scoring:
        query_token_set = set(topic.lower().split() + scripture_reference.lower().split())
        match_count     = len(query_token_set & set(quote_text.lower().split()))
        relevance_score = match_count / max(len(query_token_set), 1)

    author_weights (if supplied) multiplicatively scales relevance_score for
    the named author (other authors default to weight 1.0).

    Sort order: descending relevance_score, then ascending quote_text
    (deterministic tie-breaking; no OS-dependent ordering).

    Shortage protocol (checked against pre-top_k available count so intentional
    top_k < 3 requests do not spuriously warn):
        available == 0  → warns "[RAG_SHORTAGE][EMPTY] QuoteCatalog topic=<t> count=0"
        1 <= available < 3 → warns "[RAG_SHORTAGE][THIN] QuoteCatalog topic=<t> count=<N>"

    Never raises. Returns [] if catalog is empty or no matches within source_types.
    """

    def __init__(self, catalog_path: Path = _DEFAULT_CATALOG_PATH) -> None:
        with catalog_path.open(encoding="utf-8") as fh:
            raw = json.load(fh)
        self._quotes: List[QuoteCandidate] = [QuoteCandidate(**entry) for entry in raw]

    def retrieve_quotes(
        self,
        topic: str,
        scripture_reference: str,
        author_weights: Optional[Dict[str, float]] = None,
        top_k: int = 10,
    ) -> List[QuoteCandidate]:
        """Return up to top_k QuoteCandidates ranked by keyword relevance.

        Args:
            topic: Devotional theme (e.g. "grace").
            scripture_reference: Anchor scripture (e.g. "Ephesians 2:8").
            author_weights: Optional multiplicative weight per author name.
            top_k: Maximum number of candidates to return.

        Returns:
            List[QuoteCandidate] sorted by relevance_score desc, quote_text asc.
            May be shorter than top_k if the catalog is small.
        """
        query_token_set = set(
            topic.lower().split() + scripture_reference.lower().split()
        )

        scored: List[tuple[float, str, QuoteCandidate]] = []
        for q in self._quotes:
            quote_tokens = set(q.quote_text.lower().split())
            match_count = len(query_token_set & quote_tokens)
            score = match_count / max(len(query_token_set), 1)
            if author_weights:
                score *= author_weights.get(q.author, 1.0)
            scored.append((score, q.quote_text, q))

        # Descending score, ascending quote_text — fully deterministic
        scored.sort(key=lambda t: (-t[0], t[1]))

        # Shortage check against the full pre-top_k available count so that
        # intentional top_k < 3 requests (e.g. top_k=1) do not spuriously warn.
        available = len(scored)
        if available == 0:
            warnings.warn(
                f"[RAG_SHORTAGE][EMPTY] QuoteCatalog topic={topic!r} count=0",
                stacklevel=2,
            )
        elif available < 3:
            warnings.warn(
                f"[RAG_SHORTAGE][THIN] QuoteCatalog topic={topic!r} count={available}",
                stacklevel=2,
            )

        candidates: List[QuoteCandidate] = []
        for score, _, q in scored[:top_k]:
            candidates.append(q.model_copy(update={"relevance_score": score}))

        return candidates


