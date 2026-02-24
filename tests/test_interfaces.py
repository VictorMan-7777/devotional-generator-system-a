from src.interfaces.mock_rag import MockExpositionRAG, MockQuoteRAG
from src.interfaces.rag import (
    ExpositionRAGInterface,
    QuoteCandidate,
    QuoteRAGInterface,
    RetrievedExcerpt,
)


# ---------------------------------------------------------------------------
# Helpers — typed functions that enforce Protocol compatibility at check time
# ---------------------------------------------------------------------------

def _call_quote_rag(rag: QuoteRAGInterface, topic: str) -> list[QuoteCandidate]:
    return rag.retrieve_quotes(topic=topic, scripture_reference="Romans 8:15")


def _call_exposition_rag(
    rag: ExpositionRAGInterface,
    paragraph_type: str,
) -> list[RetrievedExcerpt]:
    return rag.retrieve_for_paragraph(
        paragraph_type=paragraph_type,
        passage_reference="Romans 8:15",
        topic="grace",
        source_types=["commentary"],
    )


# ---------------------------------------------------------------------------
# MockQuoteRAG — returns ≥3 candidates for any topic
# ---------------------------------------------------------------------------

class TestMockQuoteRAG:
    def test_returns_at_least_3_candidates_default(self):
        mock = MockQuoteRAG()
        results = mock.retrieve_quotes(topic="grace", scripture_reference="Romans 8:15")
        assert len(results) >= 3

    def test_returns_at_least_3_candidates_any_topic(self):
        mock = MockQuoteRAG()
        for topic in ["faith", "hope", "love", "redemption", "prayer"]:
            results = mock.retrieve_quotes(topic=topic, scripture_reference="John 3:16")
            assert len(results) >= 3, f"Expected ≥3 candidates for topic '{topic}'"

    def test_results_are_quote_candidates(self):
        mock = MockQuoteRAG()
        results = mock.retrieve_quotes(topic="grace", scripture_reference="Romans 8:15")
        assert all(isinstance(r, QuoteCandidate) for r in results)

    def test_candidates_have_required_fields(self):
        mock = MockQuoteRAG()
        results = mock.retrieve_quotes(topic="grace", scripture_reference="Romans 8:15")
        for candidate in results:
            assert candidate.quote_text
            assert candidate.author
            assert candidate.source_title

    def test_top_k_respected_when_larger_than_minimum(self):
        mock = MockQuoteRAG()
        results = mock.retrieve_quotes(
            topic="grace", scripture_reference="Romans 8:15", top_k=1
        )
        # top_k=1 < 3 minimum, so minimum of 3 is enforced
        assert len(results) >= 3

    def test_interface_compatible_via_typed_call(self):
        mock = MockQuoteRAG()
        results = _call_quote_rag(mock, "grace")
        assert len(results) >= 3


# ---------------------------------------------------------------------------
# MockExpositionRAG — returns excerpts for each paragraph type
# ---------------------------------------------------------------------------

class TestMockExpositionRAG:
    def test_returns_excerpts_for_context_paragraph(self):
        mock = MockExpositionRAG()
        results = mock.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="Romans 8:15",
            topic="adoption",
            source_types=["commentary"],
        )
        assert len(results) >= 1

    def test_returns_excerpts_for_theological_paragraph(self):
        mock = MockExpositionRAG()
        results = mock.retrieve_for_paragraph(
            paragraph_type="theological",
            passage_reference="Romans 8:15",
            topic="adoption",
            source_types=["reference"],
        )
        assert len(results) >= 1

    def test_results_are_retrieved_excerpts(self):
        mock = MockExpositionRAG()
        for paragraph_type in ["context", "theological"]:
            results = _call_exposition_rag(mock, paragraph_type)
            assert all(isinstance(r, RetrievedExcerpt) for r in results)

    def test_excerpts_have_required_fields(self):
        mock = MockExpositionRAG()
        results = mock.retrieve_for_paragraph(
            paragraph_type="context",
            passage_reference="Romans 8:15",
            topic="grace",
            source_types=["commentary"],
        )
        for excerpt in results:
            assert excerpt.text
            assert excerpt.source_title
            assert excerpt.author
            assert excerpt.source_type in ("commentary", "reference")

    def test_unknown_paragraph_type_returns_fallback(self):
        mock = MockExpositionRAG()
        results = mock.retrieve_for_paragraph(
            paragraph_type="unknown_type",
            passage_reference="Romans 8:15",
            topic="grace",
            source_types=["commentary"],
        )
        assert len(results) >= 1  # falls back to context fixtures

    def test_interface_compatible_via_typed_call(self):
        mock = MockExpositionRAG()
        results = _call_exposition_rag(mock, "theological")
        assert len(results) >= 1
