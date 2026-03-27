from __future__ import annotations

from pathlib import Path

from src.interfaces.rag import QuoteCandidate, RetrievedExcerpt
from src.rag.research_memory import (
    load_exposition_candidates,
    load_quote_candidates,
    load_quote_source_rankings,
    record_quote_source_outcomes,
    reset_exposition_candidate_markers,
    reset_quote_candidate_markers,
    store_exposition_candidates,
    store_quote_candidates,
)


def test_quote_research_memory_preserves_unused_and_selected_candidates(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.sqlite3"
    candidates = [
        QuoteCandidate(
            quote_text="Grace teaches the heart to trust.",
            author="Author One",
            source_title="Source One",
            publication_year=1900,
            page_or_url="p. 10",
            public_domain=True,
            relevance_score=0.9,
            citation_completeness=3,
        ),
        QuoteCandidate(
            quote_text="Grace steadies fearful hands.",
            author="Author Two",
            source_title="Source Two",
            publication_year=1901,
            page_or_url="p. 11",
            public_domain=True,
            relevance_score=0.8,
            citation_completeness=2,
        ),
    ]

    store_quote_candidates(
        db_path=db_path,
        topic="grace",
        scripture_reference="Romans 8:15",
        candidates=candidates,
        selected=candidates[0],
    )

    loaded = load_quote_candidates(
        db_path=db_path,
        topic="grace",
        scripture_reference="Romans 8:15",
    )

    assert len(loaded) == 2
    assert {item.source_title for item in loaded} == {"Source One", "Source Two"}


def test_exposition_research_memory_preserves_selected_and_unused_supports(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.sqlite3"
    excerpts = [
        RetrievedExcerpt(
            text="Job's suffering arrives without warning.",
            source_title="Matthew Henry",
            author="Matthew Henry",
            source_type="commentary",
            relevance_score=0.9,
        ),
        RetrievedExcerpt(
            text="The scene exposes integrity under pressure.",
            source_title="John Gill",
            author="John Gill",
            source_type="commentary",
            relevance_score=0.8,
        ),
    ]

    store_exposition_candidates(
        db_path=db_path,
        paragraph_type="context",
        topic="integrity under pressure",
        passage_reference="Job 1:1-5",
        excerpts=excerpts,
        selected_excerpts=excerpts[:1],
    )

    loaded = load_exposition_candidates(
        db_path=db_path,
        paragraph_type="context",
        topic="integrity under pressure",
        passage_reference="Job 1:1-5",
    )

    assert len(loaded) == 2
    assert {item.source_title for item in loaded} == {"Matthew Henry", "John Gill"}


def test_reset_quote_candidate_markers_preserves_candidates_and_clears_selection_bias(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "memory.sqlite3"
    candidate = QuoteCandidate(
        quote_text="Grace teaches the heart to trust.",
        author="Author One",
        source_title="Source One",
        publication_year=1900,
        page_or_url="p. 10",
        public_domain=True,
        relevance_score=0.9,
        citation_completeness=3,
    )
    store_quote_candidates(
        db_path=db_path,
        topic="grace",
        scripture_reference="Romans 8:15",
        candidates=[candidate],
        selected=candidate,
    )

    reset_rows = reset_quote_candidate_markers(
        db_path=db_path,
        scripture_references=["Romans 8:15"],
    )

    assert reset_rows == 1
    loaded = load_quote_candidates(
        db_path=db_path,
        topic="grace",
        scripture_reference="Romans 8:15",
    )
    assert len(loaded) == 1

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            """
            SELECT selected_count, last_selected_for_reference
            FROM quote_research_memory
            WHERE topic = ? AND scripture_reference = ?
            """,
            ("grace", "Romans 8:15"),
        ).fetchone()
    finally:
        conn.close()

    assert row == (0, "")


def test_reset_exposition_candidate_markers_preserves_candidates_and_clears_selection_bias(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "memory.sqlite3"
    excerpt = RetrievedExcerpt(
        text="Job's suffering arrives without warning.",
        source_title="Matthew Henry",
        author="Matthew Henry",
        source_type="commentary",
        relevance_score=0.9,
    )
    store_exposition_candidates(
        db_path=db_path,
        paragraph_type="context",
        topic="integrity under pressure",
        passage_reference="Job 1:1-5",
        excerpts=[excerpt],
        selected_excerpts=[excerpt],
    )

    reset_rows = reset_exposition_candidate_markers(
        db_path=db_path,
        passage_references=["Job 1:1-5"],
    )

    assert reset_rows == 1
    loaded = load_exposition_candidates(
        db_path=db_path,
        paragraph_type="context",
        topic="integrity under pressure",
        passage_reference="Job 1:1-5",
    )
    assert len(loaded) == 1

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            """
            SELECT selected_count, last_selected_for_reference
            FROM exposition_research_memory
            WHERE paragraph_type = ? AND topic = ? AND passage_reference = ?
            """,
            ("context", "integrity under pressure", "Job 1:1-5"),
        ).fetchone()
    finally:
        conn.close()

    assert row == (0, "")


def test_quote_source_rankings_learn_which_domains_produce_strong_citations(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "memory.sqlite3"
    strong = QuoteCandidate(
        quote_text="Grace teaches the heart to trust.",
        author="Author One",
        source_title="Source One",
        publication_year=1900,
        page_or_url="https://archive.org/details/work/page/10",
        citation_locator="p. 10",
        source_url="https://archive.org/details/work/page/10",
        publisher="Banner",
        publication_city="London",
        public_domain=True,
        relevance_score=0.9,
        citation_completeness=5,
    )
    weak = QuoteCandidate(
        quote_text="Grace steadies fearful hands.",
        author="Author Two",
        source_title="Source Two",
        publication_year=1901,
        page_or_url="https://ccel.org/some/work.html",
        source_url="https://ccel.org/some/work.html",
        public_domain=True,
        relevance_score=0.8,
        citation_completeness=1,
    )

    record_quote_source_outcomes(
        db_path=db_path,
        candidates=[strong, weak],
        selected=strong,
    )

    rankings = load_quote_source_rankings(db_path=db_path)
    assert rankings["archive.org"] > rankings["ccel.org"]


def test_quote_source_rankings_accumulate_attempts_without_erasing_history(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "memory.sqlite3"
    weak_one = QuoteCandidate(
        quote_text="Truth matters.",
        author="Author One",
        source_title="Source One",
        publication_year=1900,
        page_or_url="https://ccel.org/one",
        source_url="https://ccel.org/one",
        public_domain=True,
        relevance_score=0.5,
        citation_completeness=1,
    )
    weak_two = QuoteCandidate(
        quote_text="Truth still matters.",
        author="Author Two",
        source_title="Source Two",
        publication_year=1901,
        page_or_url="https://ccel.org/two",
        source_url="https://ccel.org/two",
        public_domain=True,
        relevance_score=0.4,
        citation_completeness=1,
    )
    record_quote_source_outcomes(db_path=db_path, candidates=[weak_one], selected=None)
    record_quote_source_outcomes(db_path=db_path, candidates=[weak_two], selected=None)

    rankings = load_quote_source_rankings(db_path=db_path)
    assert "ccel.org" in rankings
    assert rankings["ccel.org"] > 0.0
