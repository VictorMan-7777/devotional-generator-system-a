from __future__ import annotations

from typing import Dict, List, Optional, Protocol

from pydantic import BaseModel


class QuoteCandidate(BaseModel):
    quote_text: str
    author: str
    source_title: str
    publication_year: Optional[int] = None
    page_or_url: str
    public_domain: bool
    relevance_score: float = 1.0


class RetrievedExcerpt(BaseModel):
    text: str
    source_title: str
    author: str
    source_type: str  # "commentary" | "reference"
    relevance_score: float = 1.0


class QuoteRAGInterface(Protocol):
    def retrieve_quotes(
        self,
        topic: str,
        scripture_reference: str,
        author_weights: Optional[Dict[str, float]] = None,
        top_k: int = 10,
    ) -> List[QuoteCandidate]:
        """
        Returns candidate quotes from the Quote Catalog.
        Returns at least 3 candidates if available.
        Returns fewer if catalog is thin; triggers shortage protocol if < 3.
        """
        ...


class ExpositionRAGInterface(Protocol):
    def retrieve_for_paragraph(
        self,
        paragraph_type: str,   # "context" | "theological"
        passage_reference: str,
        topic: str,
        source_types: List[str],  # "commentary" | "reference"
    ) -> List[RetrievedExcerpt]:
        """
        Returns retrieved excerpts from approved theological sources.
        paragraph_type determines which sources are queried (FR-18).
        """
        ...
