"""reference_librarian.py — Deterministic reference librarian.

Takes resource requests (passage + worker + needs), queries the resource_catalog
DB table, and returns matching LibraryCatalogEntry records.  Escalates to
acquisition when the shelf is thin.  No LLM — fully deterministic.

The RAG agent (research_librarian.py) focuses exclusively on excerpt retrieval;
this module handles all catalog bookkeeping and escalation logic.
"""
from __future__ import annotations

from pathlib import Path

from src.models.pipeline import PassageResourceRecord
from src.rag.library_catalog import chapter_window, scripture_book, select_catalog_resources


def lookup_resources(
    *,
    scripture_reference: str,
    worker_name: str,
    requested_needs: list[str],
    purpose: str,
) -> list[PassageResourceRecord]:
    """Return catalog records for a worker's resource request.

    Queries resource_catalog (DB-backed) for resources that match the passage,
    worker, and need.  Returns PassageResourceRecord entries suitable for
    injection into a PassageResourceBundle.

    Args:
        scripture_reference: e.g. "Genesis 22:1-10"
        worker_name: e.g. "outliner" or "exposition_writer"
        requested_needs: e.g. ["exposition", "background"]
        purpose: e.g. "outline" or "shared"

    Returns:
        List of PassageResourceRecord, empty if catalog has nothing relevant.
    """
    book = scripture_book(scripture_reference)
    _window_start, _window_end, window_label = chapter_window(scripture_reference)
    window_note = (
        f"Research window for {scripture_reference}: chapters {window_label}."
        if window_label
        else f"Research window for {scripture_reference}."
    )
    records: list[PassageResourceRecord] = []
    for entry in select_catalog_resources(
        scripture_reference=scripture_reference,
        worker_name=worker_name,
        requested_needs=requested_needs,
    ):
        contains = ", ".join(entry.contains)
        records.append(
            PassageResourceRecord(
                purpose=purpose,
                role_targets=[worker_name],
                source_title=entry.title,
                author=entry.author_or_editor,
                source_type=entry.resource_type,
                excerpt_text=contains,
                note=(
                    f"{window_note} Book coverage: {book or 'unknown'}. "
                    f"Catalog says this resource contains: {contains}. "
                    f"{entry.notes}".strip()
                ),
                relevance_score=float(max(0, 100 - entry.preferred_order)),
            )
        )
    return records


def catalog_is_thin(
    *,
    scripture_reference: str,
    worker_name: str,
    requested_needs: list[str],
    minimum: int = 1,
) -> bool:
    """Return True if the catalog has fewer than minimum resources for this request."""
    matches = select_catalog_resources(
        scripture_reference=scripture_reference,
        worker_name=worker_name,
        requested_needs=requested_needs,
    )
    return len(matches) < minimum


def escalate_if_shelf_thin(
    *,
    scripture_reference: str,
    topic: str,
    worker_name: str,
    requested_needs: list[str],
    minimum: int = 2,
) -> dict:
    """Request acquisition when the catalog shelf is below minimum.

    Returns an acquisition result dict (or empty dict if shelf was sufficient).
    """
    if not catalog_is_thin(
        scripture_reference=scripture_reference,
        worker_name=worker_name,
        requested_needs=requested_needs,
        minimum=minimum,
    ):
        return {}
    from src.rag.acquisition_librarian import escalate_for_passage
    return escalate_for_passage(
        scripture_reference=scripture_reference,
        topic=topic,
        missing_kinds=requested_needs,
    )
