from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.scripture.book_ids import get_book_id
from src.scripture.retrieval import ScriptureFailureAlert, ScriptureRetriever, ScriptureResult


_CURATED_REFERENCE_PLANS: dict[tuple[str, int], list[str]] = {
    ("Exodus 19-20", 12): [
        "Exodus 19:1-4",
        "Exodus 19:5-8",
        "Exodus 19:9-13",
        "Exodus 19:14-19",
        "Exodus 19:20-25",
        "Exodus 20:1-3",
        "Exodus 20:4-6",
        "Exodus 20:7-11",
        "Exodus 20:12-14",
        "Exodus 20:15-17",
        "Exodus 20:18-21",
        "Exodus 20:22-26",
    ],
    ("Proverbs 1-2", 12): [
        "Proverbs 1:1-7",
        "Proverbs 1:8-13",
        "Proverbs 1:14-19",
        "Proverbs 1:20-23",
        "Proverbs 1:24-28",
        "Proverbs 1:29-33",
        "Proverbs 2:1-5",
        "Proverbs 2:6-8",
        "Proverbs 2:9-11",
        "Proverbs 2:12-15",
        "Proverbs 2:16-19",
        "Proverbs 2:20-22",
    ],
    ("Acts 9", 12): [
        "Acts 9:1-3",
        "Acts 9:4-6",
        "Acts 9:7-9",
        "Acts 9:10-12",
        "Acts 9:13-16",
        "Acts 9:17-19",
        "Acts 9:20-22",
        "Acts 9:23-25",
        "Acts 9:26-31",
        "Acts 9:32-35",
        "Acts 9:36-39",
        "Acts 9:40-43",
    ],
}


@dataclass(frozen=True)
class ScriptureSpan:
    book: str
    start_chapter: int
    start_verse: int | None
    end_chapter: int
    end_verse: int | None


def _parse_scripture_span(reference: str) -> ScriptureSpan:
    text = " ".join(reference.strip().split())
    if not text:
        raise ValueError("Scripture range is empty.")

    m = re.match(r"^(.+?)\s+(\d+):(\d+)\s*-\s*(\d+):(\d+)$", text)
    if m:
        book, sc, sv, ec, ev = m.groups()
        return ScriptureSpan(book=book, start_chapter=int(sc), start_verse=int(sv), end_chapter=int(ec), end_verse=int(ev))

    m = re.match(r"^(.+?)\s+(\d+):(\d+)\s*-\s*(\d+)$", text)
    if m:
        book, ch, sv, ev = m.groups()
        chapter = int(ch)
        return ScriptureSpan(book=book, start_chapter=chapter, start_verse=int(sv), end_chapter=chapter, end_verse=int(ev))

    m = re.match(r"^(.+?)\s+(\d+)\s*&\s*(\d+)$", text)
    if m:
        book, c1, c2 = m.groups()
        return ScriptureSpan(book=book, start_chapter=int(c1), start_verse=None, end_chapter=int(c2), end_verse=None)

    m = re.match(r"^(.+?)\s+(\d+)\s*-\s*(\d+)$", text)
    if m:
        book, c1, c2 = m.groups()
        return ScriptureSpan(book=book, start_chapter=int(c1), start_verse=None, end_chapter=int(c2), end_verse=None)

    m = re.match(r"^(.+?)\s+(\d+):(\d+)$", text)
    if m:
        book, ch, verse = m.groups()
        chapter = int(ch)
        v = int(verse)
        return ScriptureSpan(book=book, start_chapter=chapter, start_verse=v, end_chapter=chapter, end_verse=v)

    m = re.match(r"^(.+?)\s+(\d+)$", text)
    if m:
        book, ch = m.groups()
        chapter = int(ch)
        return ScriptureSpan(book=book, start_chapter=chapter, start_verse=None, end_chapter=chapter, end_verse=None)

    raise ValueError(
        "Unsupported scripture range format. Examples: 'Genesis 1:1-31', "
        "'Genesis 1:28-2:3', 'Genesis 1-2', 'Genesis 1 & 2'."
    )


def _normalize_reference_key(reference: str) -> str:
    text = " ".join(reference.strip().split())
    text = text.replace(" & ", "-")
    text = re.sub(r"\s*-\s*", "-", text)
    return text


def _chapter_last_verse(
    retriever: ScriptureRetriever,
    *,
    book: str,
    chapter: int,
    translation: str,
    operator_import: Path | None,
) -> int:
    last_ok = 0
    # Practical cap: Psalm 119 has 176 verses.
    for verse in range(1, 177):
        ref = f"{book} {chapter}:{verse}"
        result = retriever.retrieve(reference=ref, translation=translation, operator_import=operator_import)
        if isinstance(result, ScriptureResult):
            last_ok = verse
            continue
        if isinstance(result, ScriptureFailureAlert):
            if last_ok > 0:
                break
            raise ValueError(f"Unable to resolve chapter boundary for {book} {chapter}.")
    if last_ok == 0:
        raise ValueError(f"No verses resolved for {book} {chapter}.")
    return last_ok


def _span_verse_count(
    *,
    span: ScriptureSpan,
    retriever: ScriptureRetriever,
    translation: str,
    operator_import: Path | None,
) -> int:
    chapter_last: dict[int, int] = {}
    for chapter in range(span.start_chapter, span.end_chapter + 1):
        chapter_last[chapter] = _chapter_last_verse(
            retriever,
            book=span.book,
            chapter=chapter,
            translation=translation,
            operator_import=operator_import,
        )
    start_verse = span.start_verse or 1
    end_verse = span.end_verse or chapter_last[span.end_chapter]
    total = 0
    for chapter in range(span.start_chapter, span.end_chapter + 1):
        v_start = start_verse if chapter == span.start_chapter else 1
        v_end = end_verse if chapter == span.end_chapter else chapter_last[chapter]
        total += (v_end - v_start + 1)
    return total


def _format_reference(book: str, start: tuple[int, int], end: tuple[int, int]) -> str:
    sc, sv = start
    ec, ev = end
    if sc == ec and sv == ev:
        return f"{book} {sc}:{sv}"
    if sc == ec:
        return f"{book} {sc}:{sv}-{ev}"
    return f"{book} {sc}:{sv}-{ec}:{ev}"


def select_daily_key_verses_reference(
    *,
    reference: str,
    max_key_verses: int = 2,
) -> str:
    if max_key_verses <= 0:
        raise ValueError("max_key_verses must be > 0")
    span = _parse_scripture_span(reference)
    if get_book_id(span.book) is None:
        raise ValueError(f"Unknown scripture book: '{span.book}'")
    if span.start_verse is None or span.end_verse is None:
        return reference
    if span.start_chapter != span.end_chapter:
        mid_chapter = span.start_chapter
        if span.start_verse == span.end_verse:
            return _format_reference(span.book, (span.start_chapter, span.start_verse), (span.start_chapter, span.start_verse))
        return _format_reference(span.book, (mid_chapter, span.start_verse), (mid_chapter, min(span.start_verse + max_key_verses - 1, span.start_verse)))
    total_verses = span.end_verse - span.start_verse + 1
    if total_verses <= max_key_verses:
        return reference
    if max_key_verses == 1:
        mid = span.start_verse + ((total_verses - 1) // 2)
        return _format_reference(span.book, (span.start_chapter, mid), (span.start_chapter, mid))
    center = span.start_verse + ((total_verses - 1) // 2)
    start = max(span.start_verse, center)
    end = min(span.end_verse, start + max_key_verses - 1)
    if (end - start + 1) < max_key_verses:
        start = max(span.start_verse, end - max_key_verses + 1)
    return _format_reference(span.book, (span.start_chapter, start), (span.start_chapter, end))


def count_passage_verses(
    reference: str,
    *,
    retriever: ScriptureRetriever | None = None,
    translation: str = "NASB",
    operator_import: Path | None = None,
) -> int:
    """Return the total number of verses in a scripture reference span."""
    span = _parse_scripture_span(reference)
    active_retriever = retriever or ScriptureRetriever()
    return _span_verse_count(
        span=span,
        retriever=active_retriever,
        translation=translation,
        operator_import=operator_import,
    )


def suggest_study_window_size(
    *,
    reference: str,
    num_days: int,
    retriever: ScriptureRetriever | None = None,
    translation: str = "NASB",
    operator_import: Path | None = None,
    min_verses_per_day: int = 3,
    max_verses_per_day: int = 8,
) -> int:
    if num_days <= 0:
        raise ValueError("num_days must be > 0")
    if min_verses_per_day <= 0 or max_verses_per_day <= 0:
        raise ValueError("study window bounds must be > 0")
    if min_verses_per_day > max_verses_per_day:
        raise ValueError("min_verses_per_day cannot exceed max_verses_per_day")
    span = _parse_scripture_span(reference)
    active_retriever = retriever or ScriptureRetriever()
    total_verses = _span_verse_count(
        span=span,
        retriever=active_retriever,
        translation=translation,
        operator_import=operator_import,
    )
    average = max(1, round(total_verses / num_days))
    return max(min_verses_per_day, min(max_verses_per_day, average))


def plan_scripture_day_references(
    *,
    reference: str,
    num_days: int,
    max_verses_per_day: int = 5,
    retriever: ScriptureRetriever | None = None,
    translation: str = "NASB",
    operator_import: Path | None = None,
) -> list[str]:
    if num_days <= 0:
        raise ValueError("num_days must be > 0")
    if max_verses_per_day <= 0:
        raise ValueError("max_verses_per_day must be > 0")

    curated = _CURATED_REFERENCE_PLANS.get((_normalize_reference_key(reference), num_days))
    if curated is not None:
        return list(curated)

    span = _parse_scripture_span(reference)
    if get_book_id(span.book) is None:
        raise ValueError(f"Unknown scripture book: '{span.book}'")
    if span.end_chapter < span.start_chapter:
        raise ValueError("Scripture range end chapter must be >= start chapter.")

    active_retriever = retriever or ScriptureRetriever()
    chapter_last: dict[int, int] = {}
    for chapter in range(span.start_chapter, span.end_chapter + 1):
        chapter_last[chapter] = _chapter_last_verse(
            active_retriever,
            book=span.book,
            chapter=chapter,
            translation=translation,
            operator_import=operator_import,
        )

    start_verse = span.start_verse or 1
    end_verse = span.end_verse or chapter_last[span.end_chapter]
    if start_verse <= 0 or end_verse <= 0:
        raise ValueError("Verse numbers must be >= 1.")
    if span.start_chapter == span.end_chapter and end_verse < start_verse:
        raise ValueError("Scripture range end verse must be >= start verse.")
    if start_verse > chapter_last[span.start_chapter]:
        raise ValueError(f"Start verse out of bounds for {span.book} {span.start_chapter}.")
    if end_verse > chapter_last[span.end_chapter]:
        raise ValueError(f"End verse out of bounds for {span.book} {span.end_chapter}.")

    verse_units: list[tuple[int, int]] = []
    for chapter in range(span.start_chapter, span.end_chapter + 1):
        v_start = start_verse if chapter == span.start_chapter else 1
        v_end = end_verse if chapter == span.end_chapter else chapter_last[chapter]
        if v_end < v_start:
            raise ValueError(f"Invalid verse span in chapter {chapter}.")
        for verse in range(v_start, v_end + 1):
            verse_units.append((chapter, verse))

    total = len(verse_units)
    if total < num_days:
        raise ValueError(
            f"Scripture span has {total} verses but {num_days} sections were requested."
        )

    # Partition the requested span into num_days bins, then select a representative
    # contiguous window from each bin (up to max_verses_per_day). This intentionally
    # does not require full-coverage of every verse in the range.
    refs: list[str] = []
    for i in range(num_days):
        bin_start = (i * total) // num_days
        bin_end_exclusive = ((i + 1) * total) // num_days
        bin_size = max(1, bin_end_exclusive - bin_start)
        window = min(max_verses_per_day, bin_size)
        offset = max(0, (bin_size - window) // 2)
        start_idx = bin_start + offset
        end_idx = start_idx + window - 1
        # Retrieval currently accepts only single-chapter references. Keep each
        # selected study passage within one chapter boundary.
        start_chapter = verse_units[start_idx][0]
        while end_idx > start_idx and verse_units[end_idx][0] != start_chapter:
            end_idx -= 1
        start = verse_units[start_idx]
        end = verse_units[end_idx]
        refs.append(_format_reference(span.book, start, end))
    return refs
