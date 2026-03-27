from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from src.interfaces.rag import QuoteCandidate, RetrievedExcerpt
from src.citations.quote_citations import has_strong_quote_citation, is_url


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_research_memory (
          topic TEXT NOT NULL,
          scripture_reference TEXT NOT NULL,
          author TEXT NOT NULL,
          source_title TEXT NOT NULL,
          quote_text TEXT NOT NULL,
          original_quote_text TEXT NOT NULL DEFAULT '',
          publication_year INTEGER,
          page_or_url TEXT NOT NULL DEFAULT '',
          citation_locator TEXT NOT NULL DEFAULT '',
          source_url TEXT NOT NULL DEFAULT '',
          publisher TEXT NOT NULL DEFAULT '',
          publication_city TEXT NOT NULL DEFAULT '',
          public_domain INTEGER NOT NULL DEFAULT 1,
          relevance_score REAL NOT NULL DEFAULT 0,
          citation_completeness INTEGER NOT NULL DEFAULT 0,
          selected_count INTEGER NOT NULL DEFAULT 0,
          last_selected_for_reference TEXT NOT NULL DEFAULT '',
          PRIMARY KEY (topic, scripture_reference, author, source_title, quote_text)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS exposition_research_memory (
          paragraph_type TEXT NOT NULL,
          topic TEXT NOT NULL,
          passage_reference TEXT NOT NULL,
          source_title TEXT NOT NULL,
          author TEXT NOT NULL,
          source_type TEXT NOT NULL,
          excerpt_text TEXT NOT NULL,
          original_text TEXT NOT NULL DEFAULT '',
          relevance_score REAL NOT NULL DEFAULT 0,
          selected_count INTEGER NOT NULL DEFAULT 0,
          last_selected_for_reference TEXT NOT NULL DEFAULT '',
          PRIMARY KEY (paragraph_type, topic, passage_reference, source_title, excerpt_text)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS outline_research_memory (
          outline_key TEXT NOT NULL,
          day_number INTEGER NOT NULL,
          week_number INTEGER NOT NULL,
          passage_reference TEXT NOT NULL,
          focus_label TEXT NOT NULL DEFAULT '',
          source_kind TEXT NOT NULL DEFAULT 'planner',
          source_title TEXT NOT NULL DEFAULT '',
          notes TEXT NOT NULL DEFAULT '',
          selected_count INTEGER NOT NULL DEFAULT 0,
          last_selected_for_reference TEXT NOT NULL DEFAULT '',
          PRIMARY KEY (outline_key, day_number, passage_reference, source_kind, source_title)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_source_stats (
          source_domain TEXT NOT NULL PRIMARY KEY,
          attempts INTEGER NOT NULL DEFAULT 0,
          strong_citation_hits INTEGER NOT NULL DEFAULT 0,
          selected_hits INTEGER NOT NULL DEFAULT 0,
          last_source_url TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.commit()


def _source_domain(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    if not is_url(text):
        return ""
    try:
        host = (urlparse(text).netloc or "").lower()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def store_quote_candidates(
    *,
    db_path: Path,
    topic: str,
    scripture_reference: str,
    candidates: Iterable[QuoteCandidate],
    selected: QuoteCandidate | None = None,
) -> None:
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        selected_key = None if selected is None else (
            selected.author,
            selected.source_title,
            selected.quote_text,
        )
        for cand in candidates:
            is_selected = selected_key == (cand.author, cand.source_title, cand.quote_text)
            conn.execute(
                """
                INSERT INTO quote_research_memory (
                  topic, scripture_reference, author, source_title, quote_text,
                  original_quote_text, publication_year, page_or_url, citation_locator,
                  source_url, publisher, publication_city, public_domain,
                  relevance_score, citation_completeness, selected_count,
                  last_selected_for_reference
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(topic, scripture_reference, author, source_title, quote_text)
                DO UPDATE SET
                  original_quote_text = excluded.original_quote_text,
                  publication_year = excluded.publication_year,
                  page_or_url = excluded.page_or_url,
                  citation_locator = excluded.citation_locator,
                  source_url = excluded.source_url,
                  publisher = excluded.publisher,
                  publication_city = excluded.publication_city,
                  public_domain = excluded.public_domain,
                  relevance_score = MAX(quote_research_memory.relevance_score, excluded.relevance_score),
                  citation_completeness = MAX(quote_research_memory.citation_completeness, excluded.citation_completeness),
                  selected_count = quote_research_memory.selected_count + CASE WHEN excluded.selected_count > 0 THEN 1 ELSE 0 END,
                  last_selected_for_reference = CASE
                    WHEN excluded.selected_count > 0 THEN excluded.last_selected_for_reference
                    ELSE quote_research_memory.last_selected_for_reference
                  END
                """,
                (
                    topic,
                    scripture_reference,
                    cand.author,
                    cand.source_title,
                    cand.quote_text,
                    cand.original_quote_text,
                    cand.publication_year,
                    cand.page_or_url,
                    cand.citation_locator,
                    cand.source_url,
                    cand.publisher,
                    cand.publication_city,
                    1 if cand.public_domain else 0,
                    cand.relevance_score,
                    cand.citation_completeness,
                    1 if is_selected else 0,
                    scripture_reference if is_selected else "",
                ),
            )
        conn.commit()
    finally:
        conn.close()


def record_quote_source_outcomes(
    *,
    db_path: Path,
    candidates: Iterable[QuoteCandidate],
    selected: QuoteCandidate | None = None,
) -> None:
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        selected_key = None if selected is None else (
            selected.author,
            selected.source_title,
            selected.quote_text,
        )
        for cand in candidates:
            source_url = str(
                cand.source_url or (cand.page_or_url if is_url(cand.page_or_url) else "")
            ).strip()
            domain = _source_domain(source_url)
            if not domain:
                continue
            strong = has_strong_quote_citation(
                citation_locator=cand.citation_locator or cand.page_or_url,
                publisher=cand.publisher,
                publication_city=cand.publication_city,
            )
            is_selected = selected_key == (cand.author, cand.source_title, cand.quote_text)
            conn.execute(
                """
                INSERT INTO quote_source_stats (
                  source_domain, attempts, strong_citation_hits, selected_hits, last_source_url
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_domain)
                DO UPDATE SET
                  attempts = quote_source_stats.attempts + excluded.attempts,
                  strong_citation_hits = quote_source_stats.strong_citation_hits + excluded.strong_citation_hits,
                  selected_hits = quote_source_stats.selected_hits + excluded.selected_hits,
                  last_source_url = CASE
                    WHEN excluded.last_source_url <> '' THEN excluded.last_source_url
                    ELSE quote_source_stats.last_source_url
                  END
                """,
                (
                    domain,
                    1,
                    1 if strong else 0,
                    1 if is_selected else 0,
                    source_url,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def load_quote_source_rankings(*, db_path: Path) -> dict[str, float]:
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT source_domain, attempts, strong_citation_hits, selected_hits
            FROM quote_source_stats
            """
        ).fetchall()
        rankings: dict[str, float] = {}
        for row in rows:
            attempts = int(row["attempts"] or 0)
            strong_hits = int(row["strong_citation_hits"] or 0)
            selected_hits = int(row["selected_hits"] or 0)
            if attempts <= 0:
                rankings[str(row["source_domain"])] = 0.0
                continue
            strong_rate = strong_hits / attempts
            selected_rate = selected_hits / attempts
            sample_bonus = min(attempts, 10) / 100.0
            rankings[str(row["source_domain"])] = strong_rate + (selected_rate * 0.25) + sample_bonus
        return rankings
    finally:
        conn.close()


def load_quote_candidates(
    *,
    db_path: Path,
    topic: str,
    scripture_reference: str,
    limit: int = 100,
) -> list[QuoteCandidate]:
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT *
            FROM quote_research_memory
            WHERE topic = ? OR scripture_reference = ?
            ORDER BY relevance_score DESC, citation_completeness DESC, selected_count ASC, author ASC, quote_text ASC
            LIMIT ?
            """,
            (topic, scripture_reference, limit),
        ).fetchall()
        return [QuoteCandidate(**dict(row)) for row in rows]
    finally:
        conn.close()


def store_exposition_candidates(
    *,
    db_path: Path,
    paragraph_type: str,
    topic: str,
    passage_reference: str,
    excerpts: Iterable[RetrievedExcerpt],
    selected_excerpts: Iterable[RetrievedExcerpt],
) -> None:
    selected_keys = {(item.source_title, item.text) for item in selected_excerpts}
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        for excerpt in excerpts:
            is_selected = (excerpt.source_title, excerpt.text) in selected_keys
            conn.execute(
                """
                INSERT INTO exposition_research_memory (
                  paragraph_type, topic, passage_reference, source_title, author,
                  source_type, excerpt_text, original_text, relevance_score,
                  selected_count, last_selected_for_reference
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(paragraph_type, topic, passage_reference, source_title, excerpt_text)
                DO UPDATE SET
                  original_text = excluded.original_text,
                  relevance_score = MAX(exposition_research_memory.relevance_score, excluded.relevance_score),
                  selected_count = exposition_research_memory.selected_count + CASE WHEN excluded.selected_count > 0 THEN 1 ELSE 0 END,
                  last_selected_for_reference = CASE
                    WHEN excluded.selected_count > 0 THEN excluded.last_selected_for_reference
                    ELSE exposition_research_memory.last_selected_for_reference
                  END
                """,
                (
                    paragraph_type,
                    topic,
                    passage_reference,
                    excerpt.source_title,
                    excerpt.author,
                    excerpt.source_type,
                    excerpt.text,
                    excerpt.original_text,
                    excerpt.relevance_score,
                    1 if is_selected else 0,
                    passage_reference if is_selected else "",
                ),
            )
        conn.commit()
    finally:
        conn.close()


def load_exposition_candidates(
    *,
    db_path: Path,
    paragraph_type: str,
    topic: str,
    passage_reference: str,
    limit: int = 100,
) -> list[RetrievedExcerpt]:
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT *
            FROM exposition_research_memory
            WHERE paragraph_type = ?
              AND (topic = ? OR passage_reference = ?)
            ORDER BY relevance_score DESC, selected_count ASC, source_title ASC, excerpt_text ASC
            LIMIT ?
            """,
            (paragraph_type, topic, passage_reference, limit),
        ).fetchall()
        return [
            RetrievedExcerpt(
                text=row["excerpt_text"],
                original_text=row["original_text"],
                source_title=row["source_title"],
                author=row["author"],
                source_type=row["source_type"],
                relevance_score=float(row["relevance_score"]),
            )
            for row in rows
        ]
    finally:
        conn.close()


def reset_quote_candidate_markers(
    *,
    db_path: Path,
    scripture_references: Iterable[str] = (),
    topics: Iterable[str] = (),
) -> int:
    references = [str(item).strip() for item in scripture_references if str(item).strip()]
    topic_values = [str(item).strip() for item in topics if str(item).strip()]
    if not references and not topic_values:
        return 0

    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        clauses: list[str] = []
        params: list[str] = []
        if references:
            clauses.append(
                "scripture_reference IN ({})".format(",".join("?" for _ in references))
            )
            params.extend(references)
        if topic_values:
            clauses.append("topic IN ({})".format(",".join("?" for _ in topic_values)))
            params.extend(topic_values)
        cursor = conn.execute(
            f"""
            UPDATE quote_research_memory
            SET selected_count = 0,
                last_selected_for_reference = ''
            WHERE {' OR '.join(clauses)}
            """,
            params,
        )
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def reset_exposition_candidate_markers(
    *,
    db_path: Path,
    passage_references: Iterable[str] = (),
    topics: Iterable[str] = (),
) -> int:
    references = [str(item).strip() for item in passage_references if str(item).strip()]
    topic_values = [str(item).strip() for item in topics if str(item).strip()]
    if not references and not topic_values:
        return 0

    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        clauses: list[str] = []
        params: list[str] = []
        if references:
            clauses.append(
                "passage_reference IN ({})".format(",".join("?" for _ in references))
            )
            params.extend(references)
        if topic_values:
            clauses.append("topic IN ({})".format(",".join("?" for _ in topic_values)))
            params.extend(topic_values)
        cursor = conn.execute(
            f"""
            UPDATE exposition_research_memory
            SET selected_count = 0,
                last_selected_for_reference = ''
            WHERE {' OR '.join(clauses)}
            """,
            params,
        )
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def store_outline_research(
    *,
    db_path: Path,
    outline_key: str,
    rows: Iterable[dict[str, object]],
    source_kind: str,
    source_title: str = "",
    notes: str = "",
) -> None:
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        for row in rows:
            day_number = int(row.get("day", 0) or row.get("day_number", 0) or 0)
            week_number = int(row.get("week", 0) or row.get("week_number", 0) or 0)
            passage_reference = str(row.get("reference") or row.get("scripture_reference") or "").strip()
            focus_label = str(row.get("focus") or row.get("focus_label") or "").strip()
            if day_number <= 0 or week_number <= 0 or not passage_reference:
                continue
            conn.execute(
                """
                INSERT INTO outline_research_memory (
                  outline_key, day_number, week_number, passage_reference,
                  focus_label, source_kind, source_title, notes,
                  selected_count, last_selected_for_reference
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(outline_key, day_number, passage_reference, source_kind, source_title)
                DO UPDATE SET
                  focus_label = excluded.focus_label,
                  notes = excluded.notes
                """,
                (
                    outline_key,
                    day_number,
                    week_number,
                    passage_reference,
                    focus_label,
                    source_kind,
                    source_title,
                    notes,
                    0,
                    "",
                ),
            )
        conn.commit()
    finally:
        conn.close()


def load_outline_candidates(
    *,
    db_path: Path,
    scripture_reference: str,
    limit: int = 12,
) -> list[dict[str, object]]:
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        ref = str(scripture_reference or "").strip()
        book_prefix = ref.split()[0].lower() if ref else ""
        rows = conn.execute(
            """
            SELECT outline_key, day_number, week_number, passage_reference,
                   focus_label, source_kind, source_title, notes, selected_count
            FROM outline_research_memory
            WHERE lower(passage_reference) = lower(?)
               OR lower(passage_reference) LIKE ?
            ORDER BY selected_count DESC, day_number ASC
            LIMIT ?
            """,
            (
                ref,
                f"{book_prefix}%" if book_prefix else ref,
                int(limit),
            ),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
