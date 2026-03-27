"""catalog.py — Phase 005 CP1 QuoteCatalog: concrete QuoteRAGInterface implementation.

Loads quote data from a JSON seed file at construction time. Retrieval is
deterministic: keyword-overlap scoring, then alphabetical tie-breaking.
No LLM calls. No network calls. No embeddings.

Shortage protocol: if the result set has < 3 candidates, emits a structured
warnings.warn() message and returns all available candidates without raising.
"""
from __future__ import annotations

import json
import os
import warnings
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from src.citations.quote_citations import (
    is_url,
    normalize_quote_citation_fields,
    quote_citation_completeness,
)
from src.interfaces.rag import QuoteCandidate
from src.persistence.paths import default_registry_db_path
from src.rag.sqlite_catalog import load_quote_rows

_DEFAULT_CATALOG_PATH = (
    Path(__file__).parent.parent.parent / "data" / "quotes" / "seed-quotes.json"
)

_APPROVED_AUTHORS = {
    "Martin Luther",
    "John Calvin",
    "Richard Sibbes",
    "Samuel Rutherford",
    "Richard Baxter",
    "John Owen",
    "Thomas Watson",
    "John Bunyan",
    "Matthew Henry",
    "William Law",
    "Samuel Hopkins",
    "George Whitefield",
    "John Wesley",
    "Jonathan Edwards",
    "John Fletcher",
    "Charles H. Spurgeon",
    "Arthur W. Pink",
}

_APPROVED_SOURCE_DOMAINS = {
    "ccel.org",
    "archive.org",
    "gutenberg.org",
    "monergism.com",
    "spurgeongems.org",
    "grace-ebooks.com",
    "classicchristianlibrary.com",
    "wesley.nnu.edu",
}


def _approved_source_url(url: str) -> bool:
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    host = (parsed.netloc or "").lower()
    if not host:
        return False
    if host.startswith("www."):
        host = host[4:]
    return host in _APPROVED_SOURCE_DOMAINS


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
        resolved_catalog = Path(catalog_path).resolve()
        if resolved_catalog == _DEFAULT_CATALOG_PATH.resolve():
            db_path = default_registry_db_path()
            strict_db_only = os.getenv("DEVG_REQUIRE_DB_CATALOG", "").strip() == "1"
            raw = load_quote_rows(
                db_path=db_path,
                seed_path=resolved_catalog,
                strict_db_only=strict_db_only,
            )
        else:
            with resolved_catalog.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        self._quotes: List[QuoteCandidate] = [
            QuoteCandidate(**normalize_quote_citation_fields(entry))
            for entry in raw
        ]
        if resolved_catalog == _DEFAULT_CATALOG_PATH.resolve():
            violations: list[str] = []
            for i, q in enumerate(self._quotes, start=1):
                if q.author not in _APPROVED_AUTHORS:
                    violations.append(f"entry#{i}: author {q.author!r} not in approved whitelist")
                if not (1483 <= int(q.publication_year or 0) <= 1952):
                    violations.append(
                        f"entry#{i}: publication_year {q.publication_year!r} outside 1483-1952"
                    )
                source_url = str(q.source_url or "").strip()
                if not source_url and is_url(str(q.page_or_url)):
                    source_url = str(q.page_or_url).strip()
                if not _approved_source_url(source_url):
                    violations.append(
                        f"entry#{i}: source_url {source_url or q.page_or_url!r} is not an approved source URL"
                    )
            if violations:
                raise ValueError(
                    "Default quote catalog violates approved source policy: " + "; ".join(violations)
                )

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
            candidates.append(
                q.model_copy(
                    update={
                        "relevance_score": score,
                        "citation_completeness": quote_citation_completeness(
                            citation_locator=q.citation_locator,
                            publisher=q.publisher,
                            publication_city=q.publication_city,
                            source_url=q.source_url or (q.page_or_url if is_url(q.page_or_url) else ""),
                        ),
                    }
                )
            )

        return candidates
