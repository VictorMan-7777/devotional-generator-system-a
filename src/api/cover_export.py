"""cover_export.py — Cover generation wrapper for the devotional pipeline.

Generates KDP-ready full-wrap cover PDFs (and PNG review copies) for all three
design concepts from a DevotionalBook. The cover is a separate KDP artifact —
it is not embedded in the content PDF.

Usage (after generate_devotional):

    from src.api.cover_export import generate_cover_for_book
    cover_paths = generate_cover_for_book(
        result.book,
        output_dir=Path("outputs/my-series/cover"),
        title="Walking Through Ruth",
        subtitle="A 6-Day Reformed Devotional",
        author="Sacred Whispers Publishing",
        blurb="Six days in the faithfulness of Ruth and Boaz...",
    )
    # cover_paths == {"shepherds_rest": {"png": Path(...), "pdf": Path(...)}, ...}
"""
from __future__ import annotations

from pathlib import Path

from src.cover.concepts import ALL_CONCEPTS
from src.cover.engine import render_cover
from src.models.devotional import DevotionalBook


def _estimate_page_count(book: DevotionalBook) -> int:
    """Rough page count: ~8 pages/day, minimum 60 (KDP spine requires >=24 pages)."""
    return max(60, len(book.days) * 8)


def generate_cover_for_book(
    book: DevotionalBook,
    *,
    output_dir: Path,
    title: str | None = None,
    subtitle: str | None = None,
    author: str = "Sacred Whispers Publishing",
    blurb: str | None = None,
    website: str = "sacredwhisperspublishing.com",
) -> dict[str, dict[str, Path]]:
    """Generate all 3 KDP cover concepts for a DevotionalBook.

    Args:
        book: The DevotionalBook from generate_devotional().
        output_dir: Directory to write PNG and PDF files into.
        title: Cover title. Defaults to book.input.title or book.input.topic.
        subtitle: Subtitle line. Defaults to "{N}-Day Reformed Daily Devotional".
        author: Author/publisher name on cover spine and front.
        blurb: Back-cover blurb. Defaults to a short passage-based description.
        website: URL shown on back cover.

    Returns:
        dict mapping design_id → {"png": Path, "pdf": Path} for each concept.
        Three entries: "shepherds_rest", "still_waters", "sanctuary".
    """
    output_dir = Path(output_dir)

    resolved_title = title or book.input.title or book.input.topic
    resolved_subtitle = (
        subtitle or f"A {len(book.days)}-Day Reformed Daily Devotional"
    )
    resolved_blurb = blurb or (
        f"A {len(book.days)}-day journey through {book.input.topic}, "
        "grounded in the Reformed evangelical tradition. "
        "Each day draws from the text to produce passage-faithful exposition, "
        "meditative stillness, and concrete application."
    )

    page_count = _estimate_page_count(book)

    results: dict[str, dict[str, Path]] = {}
    for concept in ALL_CONCEPTS:
        paths = render_cover(
            concept,
            title=resolved_title,
            subtitle=resolved_subtitle,
            author=author,
            blurb=resolved_blurb,
            website=website,
            page_count=page_count,
            output_dir=output_dir,
        )
        results[concept.design_id] = paths

    return results
