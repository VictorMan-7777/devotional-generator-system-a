from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.models.pipeline import PassageResourceBundle, PassageResourceRecord
from src.rag.exposition import ExpositionRAG
from src.rag.library_catalog import chapter_window, scripture_book, select_catalog_resources
from src.rag.library_requests import (
    list_resource_acquisition_requests,
    request_resource_acquisition,
    update_resource_acquisition_request,
)
from src.rag.research_memory import load_outline_candidates

_READING_NOTES_DIR = Path(__file__).resolve().parents[2] / "data" / "library" / "reading-notes" / "drafts"


def _load_reading_note_hints() -> list[PassageResourceRecord]:
    """Load research_librarian_memory sentences from reading notes as shared resource hints.

    These are one-liner descriptions of each library resource (e.g. "Remember Matthew
    Henry first for background, citation, exposition, quotes.").  They are general —
    not passage-specific — and serve as lightweight resource-awareness hints for workers
    until passage-level indexing is complete.
    """
    hints: list[PassageResourceRecord] = []
    if not _READING_NOTES_DIR.exists():
        return hints
    for note_path in sorted(_READING_NOTES_DIR.glob("*.json")):
        if "evaluation" in note_path.name:
            continue
        try:
            note = json.loads(note_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        memory = str(note.get("research_librarian_memory") or "").strip()
        if not memory:
            continue
        title = str(note.get("title") or note_path.stem).strip()
        author = str(note.get("author_or_editor") or "").strip()
        hints.append(
            PassageResourceRecord(
                purpose="shared",
                role_targets=["outliner", "exposition_writer"],
                source_title=title,
                author=author,
                source_type="library-reading-note",
                excerpt_text=memory,
                note="Research librarian memory — general resource guidance, not passage-specific.",
                relevance_score=0.5,
            )
        )
    return hints


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _book_hint(reference: str) -> str:
    return str(reference or "").split(":", 1)[0].strip()


def prepare_passage_resource_bundle(
    *,
    topic: str,
    scripture_reference: str,
    db_path: Path,
) -> PassageResourceBundle:
    reference = str(scripture_reference or "").strip()
    if not reference:
        return PassageResourceBundle(
            topic=topic,
            scripture_reference="",
            prepared_at_utc=_utc_now(),
        )

    rag = ExpositionRAG()
    queries: list[str] = []
    for item in (topic, reference, _book_hint(reference)):
        cleaned = str(item or "").strip()
        if cleaned and cleaned not in queries:
            queries.append(cleaned)

    context_entries: list[PassageResourceRecord] = []
    theological_entries: list[PassageResourceRecord] = []
    seen: set[tuple[str, str, str, str]] = set()
    for query in queries:
        for purpose, bucket in (
            ("context", context_entries),
            ("theological", theological_entries),
        ):
            for excerpt in rag.retrieve_for_paragraph(
                paragraph_type=purpose,
                passage_reference=reference,
                topic=query,
                source_types=["commentary", "reference"],
            ):
                key = (purpose, excerpt.source_title, excerpt.author, excerpt.text)
                if key in seen:
                    continue
                seen.add(key)
                bucket.append(
                    PassageResourceRecord(
                        purpose=purpose,
                        role_targets=["outliner", "exposition_writer"],
                        source_title=excerpt.source_title,
                        author=excerpt.author,
                        source_type=excerpt.source_type,
                        excerpt_text=excerpt.text,
                        note=f"Research librarian prepared {purpose} support for {reference}.",
                        relevance_score=float(excerpt.relevance_score),
                    )
                )
                if len(bucket) >= 8:
                    break

    outline_rows = load_outline_candidates(
        db_path=db_path,
        scripture_reference=reference,
        limit=8,
    )
    outliner_resources = [
        PassageResourceRecord(
            purpose="outline",
            role_targets=["outliner"],
            source_title=str(
                row.get("source_title") or row.get("outline_key") or "outline-memory"
            ),
            source_type=str(row.get("source_kind") or "outline-memory"),
            excerpt_text=str(row.get("focus_label") or "").strip(),
            note=str(row.get("notes") or row.get("passage_reference") or "").strip(),
            relevance_score=float(row.get("selected_count") or 0.0),
        )
        for row in outline_rows
    ]
    outliner_resources = _dedupe_resource_records(
        outliner_resources
        + _catalog_records_for_worker(
            scripture_reference=reference,
            worker_name="outliner",
            requested_needs=["outline", "structure", "background"],
            purpose="outline",
        )
    )

    shared_resources: list[PassageResourceRecord] = []
    shared_seen: set[tuple[str, str, str]] = set()
    for entry in context_entries + theological_entries:
        key = (entry.source_title, entry.author, entry.source_type)
        if key in shared_seen:
            continue
        shared_seen.add(key)
        shared_resources.append(
            PassageResourceRecord(
                purpose="shared",
                role_targets=["outliner", "exposition_writer"],
                source_title=entry.source_title,
                author=entry.author,
                source_type=entry.source_type,
                note=f"Shared library resource prepositioned for {reference}.",
                relevance_score=entry.relevance_score,
            )
        )
        if len(shared_resources) >= 10:
            break
    for entry in _catalog_records_for_worker(
        scripture_reference=reference,
        worker_name="exposition_writer",
        requested_needs=["exposition", "background", "terms"],
        purpose="shared",
    ):
        key = (entry.source_title, entry.author, entry.source_type)
        if key in shared_seen:
            continue
        shared_seen.add(key)
        shared_resources.append(entry)
        if len(shared_resources) >= 10:
            break

    # Augment shared_resources with reading-note hints (one-liner resource
    # memory sentences) so workers know what library holdings are available
    # even before passage-level text is indexed.
    reading_note_hints = _load_reading_note_hints()
    for hint in reading_note_hints:
        key = (hint.source_title, hint.author, hint.source_type)
        if key not in shared_seen:
            shared_seen.add(key)
            shared_resources.append(hint)

    bundle = PassageResourceBundle(
        topic=topic,
        scripture_reference=reference,
        prepared_at_utc=_utc_now(),
        shared_resources=shared_resources,
        outliner_resources=outliner_resources,
        exposition_resources=context_entries + theological_entries,
    )
    _request_trainer_review_if_thin(bundle)
    return bundle


def clear_requests_satisfied_by_current_holdings(
    actionable_requests: list[dict[str, object]],
) -> list[str]:
    cleared: list[str] = []
    for item in actionable_requests:
        request_id = str(item.get("request_id") or "").strip()
        if not request_id:
            continue
        matches = int(item.get("matching_current_holdings") or 0)
        reference = str(item.get("scripture_reference") or "").strip()
        update_resource_acquisition_request(
            request_id=request_id,
            status="answered",
            notes=(
                "Research librarian cleared acquisition after trainer review. "
                f"Current shelf already had {matches} matching holdings for {reference}; "
                "serve from current holdings before escalating again."
            ),
            completed_at_utc=_utc_now(),
        )
        cleared.append(request_id)
    return cleared


def clear_stale_requests_when_shelf_is_sufficient(
    *,
    worker_name: str = "outliner",
    minimum_matches: int = 3,
) -> list[str]:
    cleared: list[str] = []
    for status in ("requested", "trainer_review"):
        for request in list_resource_acquisition_requests(
            requested_by="research_librarian",
            status=status,
        ):
            matches = select_catalog_resources(
                scripture_reference=request.scripture_reference,
                worker_name=worker_name,
                requested_needs=list(request.requested_resource_kinds or ["background"]),
            )
            if len(matches) < minimum_matches:
                continue
            update_resource_acquisition_request(
                request_id=request.request_id,
                status="answered",
                notes=(
                    "Research librarian cleared acquisition because current holdings were already sufficient. "
                    f"Shelf matches found: {len(matches)} for {request.scripture_reference}."
                ),
                completed_at_utc=_utc_now(),
            )
            cleared.append(request.request_id)
    return cleared


def apply_library_trainer_review(
    actionable_requests: list[dict[str, object]],
) -> dict[str, list[str]]:
    cleared: list[str] = []
    approved: list[str] = []
    for item in actionable_requests:
        request_id = str(item.get("request_id") or "").strip()
        resolution = str(item.get("recommended_resolution") or "").strip()
        reference = str(item.get("scripture_reference") or "").strip()
        matches = int(item.get("matching_current_holdings") or 0)
        if not request_id or not resolution:
            continue
        if resolution == "clear_and_serve_from_current_holdings":
            update_resource_acquisition_request(
                request_id=request_id,
                status="answered",
                notes=(
                    "Library trainer reviewed this request and directed the research librarian to use current holdings. "
                    f"Shelf matches found: {matches} for {reference}."
                ),
                completed_at_utc=_utc_now(),
            )
            cleared.append(request_id)
        elif resolution == "approve_for_acquisition_librarian":
            update_resource_acquisition_request(
                request_id=request_id,
                status="requested",
                notes=(
                    "Library trainer approved this request for acquisition-librarian acquisition after reviewing current holdings."
                ),
                completed_at_utc="",
            )
            approved.append(request_id)
    return {"cleared_request_ids": cleared, "approved_request_ids": approved}


def _request_trainer_review_if_thin(bundle: PassageResourceBundle) -> None:
    missing_kinds: list[str] = []
    if len(bundle.exposition_resources) < 4:
        missing_kinds.append("exposition")
    if len(bundle.outliner_resources) < 2:
        missing_kinds.append("outline")
    if not missing_kinds:
        return
    request_resource_acquisition(
        requested_by="research_librarian",
        scripture_reference=bundle.scripture_reference,
        topic=bundle.topic,
        worker_name="research_librarian",
        reason=(
            "Shared passage bundle is too thin for reliable worker use. "
            f"Missing strength in: {', '.join(missing_kinds)}."
        ),
        requested_resource_kinds=missing_kinds,
        status="trainer_review",
        notes=(
            "Trainer review required before this can become a general-librarian acquisition request. "
            "Research librarian is still in shelf-identification training."
        ),
    )


def _catalog_records_for_worker(
    *,
    scripture_reference: str,
    worker_name: str,
    requested_needs: list[str],
    purpose: str,
) -> list[PassageResourceRecord]:
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


def _dedupe_resource_records(
    records: list[PassageResourceRecord],
) -> list[PassageResourceRecord]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[PassageResourceRecord] = []
    for record in records:
        key = (
            record.purpose,
            record.source_title,
            record.author,
            record.source_type,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped
