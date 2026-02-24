from __future__ import annotations

from typing import Dict, List, Optional

from src.interfaces.rag import (
    ExpositionRAGInterface,
    QuoteCandidate,
    QuoteRAGInterface,
    RetrievedExcerpt,
)

_FIXTURE_QUOTES: List[QuoteCandidate] = [
    QuoteCandidate(
        quote_text="All is grace.",
        author="Thomas Merton",
        source_title="Thoughts in Solitude",
        publication_year=1958,
        page_or_url="p. 42",
        public_domain=False,
        relevance_score=0.95,
    ),
    QuoteCandidate(
        quote_text=(
            "The life of faith is not a life of mounting up with wings, "
            "but a life of walking and not fainting."
        ),
        author="Oswald Chambers",
        source_title="My Utmost for His Highest",
        publication_year=1935,
        page_or_url="January 5",
        public_domain=True,
        relevance_score=0.87,
    ),
    QuoteCandidate(
        quote_text=(
            "To be grateful is to recognize the Love of God in everything He has given us."
        ),
        author="Thomas Merton",
        source_title="Thoughts in Solitude",
        publication_year=1958,
        page_or_url="p. 33",
        public_domain=False,
        relevance_score=0.82,
    ),
    QuoteCandidate(
        quote_text="Prayer is not asking. It is a longing of the soul.",
        author="Mahatma Gandhi",
        source_title="Young India",
        publication_year=1925,
        page_or_url="n/a",
        public_domain=True,
        relevance_score=0.76,
    ),
]

_FIXTURE_CONTEXT_EXCERPTS: List[RetrievedExcerpt] = [
    RetrievedExcerpt(
        text=(
            "The Roman letter was written to a community struggling to understand "
            "the relationship between Jewish heritage and Gentile inclusion."
        ),
        source_title="Romans: An Exegetical Commentary",
        author="Thomas Schreiner",
        source_type="commentary",
        relevance_score=0.92,
    ),
    RetrievedExcerpt(
        text=(
            "Paul's use of 'spirit of adoption' (huiothesias) draws on "
            "Greco-Roman legal practice to illuminate the believer's new status."
        ),
        source_title="Word Biblical Commentary: Romans",
        author="James Dunn",
        source_type="commentary",
        relevance_score=0.88,
    ),
]

_FIXTURE_THEOLOGICAL_EXCERPTS: List[RetrievedExcerpt] = [
    RetrievedExcerpt(
        text=(
            "The doctrine of adoption is one of the richest concepts in Pauline theology, "
            "describing the transfer from slavery to full sonship."
        ),
        source_title="Systematic Theology",
        author="Wayne Grudem",
        source_type="reference",
        relevance_score=0.91,
    ),
    RetrievedExcerpt(
        text=(
            "Union with Christ grounds all aspects of the believer's relationship with God, "
            "including justification, adoption, and sanctification."
        ),
        source_title="Knowing God",
        author="J.I. Packer",
        source_type="reference",
        relevance_score=0.89,
    ),
]

_PARAGRAPH_FIXTURES: Dict[str, List[RetrievedExcerpt]] = {
    "context": _FIXTURE_CONTEXT_EXCERPTS,
    "theological": _FIXTURE_THEOLOGICAL_EXCERPTS,
}


class MockQuoteRAG:
    """Mock implementation of QuoteRAGInterface returning fixture data."""

    def retrieve_quotes(
        self,
        topic: str,
        scripture_reference: str,
        author_weights: Optional[Dict[str, float]] = None,
        top_k: int = 10,
    ) -> List[QuoteCandidate]:
        count = max(3, min(top_k, len(_FIXTURE_QUOTES)))
        return _FIXTURE_QUOTES[:count]


class MockExpositionRAG:
    """Mock implementation of ExpositionRAGInterface returning fixture data."""

    def retrieve_for_paragraph(
        self,
        paragraph_type: str,
        passage_reference: str,
        topic: str,
        source_types: List[str],
    ) -> List[RetrievedExcerpt]:
        return _PARAGRAPH_FIXTURES.get(paragraph_type, _FIXTURE_CONTEXT_EXCERPTS)


# Structural compatibility assertions (verified at import time by type checkers)
_: QuoteRAGInterface = MockQuoteRAG()
__: ExpositionRAGInterface = MockExpositionRAG()
