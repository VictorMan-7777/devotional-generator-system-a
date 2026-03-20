from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.models.pipeline import PassageResourceBundle, PassageResourceRecord
from src.rag.exposition import ExpositionRAG
from src.rag.acquisition_librarian import escalate_for_passage
from src.rag.library_catalog import scripture_book, select_catalog_resources
from src.rag.reference_librarian import lookup_resources as _catalog_lookup
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
    num_days: int = 1,
    day_plan: list[dict] | None = None,
    _skip_escalation: bool = False,
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

    # --- Seminary librarian curation (LLM) ---
    # Ask the LLM to evaluate the bundle, annotate each resource with passage-
    # specific notes, and identify gaps.  Disabled when API key is absent or
    # when explicitly skipped (e.g., on the rebuild pass after acquisition).
    all_exposition = context_entries + theological_entries
    librarian_assessment: dict | None = None
    if not _skip_escalation and os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        try:
            from src.rag.llm_research_librarian_core import curate_passage_bundle
            raw_excerpts = [
                {
                    "source_title": r.source_title,
                    "author": r.author,
                    "text": r.excerpt_text or "",
                    "source_type": r.source_type,
                    "relevance_score": r.relevance_score or 0.0,
                }
                for r in all_exposition
            ]
            hint_texts = [h.excerpt_text or "" for h in reading_note_hints if h.excerpt_text]
            librarian_assessment = curate_passage_bundle(
                passage_reference=reference,
                topic=topic or reference,
                candidate_excerpts=raw_excerpts,
                reading_note_hints=hint_texts,
            )
            # Annotate resources with the librarian's passage-specific notes
            annotation_map = {
                a["source_title"]: a
                for a in librarian_assessment.get("resource_annotations", [])
            }
            for record in all_exposition:
                ann = annotation_map.get(record.source_title)
                if ann:
                    record = PassageResourceRecord(
                        purpose=record.purpose,
                        role_targets=record.role_targets,
                        source_title=record.source_title,
                        author=record.author,
                        source_type=record.source_type,
                        excerpt_text=record.excerpt_text,
                        note=ann.get("passage_relevance") or record.note,
                        relevance_score=(
                            record.relevance_score + (0.1 if ann.get("priority") == "primary" else 0)
                        ),
                    )
            # Surface suggested search terms as additional queries if bundle is thin
            if librarian_assessment.get("bundle_assessment") == "thin":
                extra_queries = librarian_assessment.get("suggested_search_terms", [])
                seen_extra: set[tuple] = {
                    (r.source_title, r.author, r.source_type, r.excerpt_text)
                    for r in all_exposition
                }
                for extra_q in extra_queries[:2]:
                    for purpose, bucket in (
                        ("context", context_entries),
                        ("theological", theological_entries),
                    ):
                        for excerpt in rag.retrieve_for_paragraph(
                            paragraph_type=purpose,
                            passage_reference=reference,
                            topic=extra_q,
                            source_types=["commentary", "reference"],
                        ):
                            key = (purpose, excerpt.source_title, excerpt.author, excerpt.text)
                            if key not in seen:
                                seen.add(key)
                                seen_extra.add(key)
                                bucket.append(
                                    PassageResourceRecord(
                                        purpose=purpose,
                                        role_targets=["outliner", "exposition_writer"],
                                        source_title=excerpt.source_title,
                                        author=excerpt.author,
                                        source_type=excerpt.source_type,
                                        excerpt_text=excerpt.text,
                                        note=f"Librarian supplemental search ({extra_q!r}).",
                                        relevance_score=float(excerpt.relevance_score),
                                    )
                                )
                            if len(bucket) >= 10:
                                break
        except Exception:
            pass  # LLM unavailable — fall back to deterministic bundle silently

    # --- Per-day exposition packages for the writer ---
    # When a day_plan is supplied the research librarian curates a focused set
    # of exposition resources for each day's specific passage.  The outliner
    # always receives the full-arc outliner_resources (no per-day split).
    exposition_resources_by_day: dict[int, list[PassageResourceRecord]] = {}
    if day_plan:
        for day_num, day_row in enumerate(day_plan, start=1):
            day_ref = str(day_row.get("scripture_reference") or reference).strip() or reference
            day_topic = str(day_row.get("topic") or topic).strip() or topic
            day_entries: list[PassageResourceRecord] = []
            day_seen: set[tuple[str, str, str, str]] = set()
            for purpose in ("context", "theological"):
                for excerpt in rag.retrieve_for_paragraph(
                    paragraph_type=purpose,
                    passage_reference=day_ref,
                    topic=day_topic,
                    source_types=["commentary", "reference"],
                ):
                    key = (purpose, excerpt.source_title, excerpt.author, excerpt.text)
                    if key in day_seen:
                        continue
                    day_seen.add(key)
                    day_entries.append(
                        PassageResourceRecord(
                            purpose=purpose,
                            role_targets=["exposition_writer"],
                            source_title=excerpt.source_title,
                            author=excerpt.author,
                            source_type=excerpt.source_type,
                            excerpt_text=excerpt.text,
                            note=f"Day {day_num} exposition resource for {day_ref}.",
                            relevance_score=float(excerpt.relevance_score),
                        )
                    )
                    if len(day_entries) >= 6:
                        break
                if len(day_entries) >= 6:
                    break
            exposition_resources_by_day[day_num] = day_entries

    bundle = PassageResourceBundle(
        topic=topic,
        scripture_reference=reference,
        prepared_at_utc=_utc_now(),
        shared_resources=shared_resources,
        outliner_resources=outliner_resources,
        exposition_resources=context_entries + theological_entries,
        exposition_resources_by_day=exposition_resources_by_day,
    )

    acquired = False if _skip_escalation else _escalate_if_thin(bundle)
    if acquired:
        # New material was indexed — rebuild the bundle so this generation
        # run benefits from it rather than waiting until the next run.
        print(
            f"[Research Librarian] New resources acquired for {reference} — "
            "rebuilding bundle with fresh catalog...",
            flush=True,
        )
        return prepare_passage_resource_bundle(
            topic=topic,
            scripture_reference=reference,
            db_path=db_path,
            num_days=num_days,
            day_plan=day_plan,
            _skip_escalation=True,
        )

    return bundle


def request_more_research(
    *,
    scripture_reference: str,
    topic: str,
    reason: str,
    requested_by: str = "exposition_writer",
    missing_kinds: list[str] | None = None,
) -> dict:
    """Called by any worker that is unhappy with its research bundle.

    Triggers a full acquisition escalation so the librarian can source
    additional materials.  Safe to call multiple times for the same passage —
    escalate_for_passage() is idempotent.

    Args:
        scripture_reference: The passage the worker needs more material on.
        topic: The devotional topic context.
        reason: Why the current bundle was insufficient (shown in logs/DB).
        requested_by: Which worker is requesting (e.g. 'exposition_writer').
        missing_kinds: Which resource types are thin ('exposition', 'outline').
    """
    kinds = missing_kinds or ["exposition"]
    print(
        f"\n[Research Librarian] {requested_by} requested more research for "
        f"{scripture_reference}: {reason}",
        flush=True,
    )
    return escalate_for_passage(
        scripture_reference=scripture_reference,
        topic=topic,
        missing_kinds=kinds,
    )


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
            # Note: select_catalog_resources is still used here (not reference_librarian)
            # because this path counts catalog entries directly (not PassageResourceRecord objs).
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


def _escalate_if_thin(bundle: PassageResourceBundle) -> bool:
    """Run the acquisition pipeline if the bundle is thin.

    Returns True if new material was indexed (caller should rebuild the bundle).
    Returns False if nothing was needed or nothing new was found.
    """
    missing_kinds: list[str] = []
    if len(bundle.exposition_resources) < 4:
        missing_kinds.append("exposition")
    if len(bundle.outliner_resources) < 2:
        missing_kinds.append("outline")
    if not missing_kinds:
        return False
    # Record a trainer-review request so the library trainer can assess the gap.
    # This call uses the local import so it can be observed/intercepted by callers.
    request_resource_acquisition(
        requested_by="research_librarian",
        scripture_reference=bundle.scripture_reference,
        topic=bundle.topic or "",
        reason=(
            f"Research librarian bundle thin for {bundle.scripture_reference}. "
            f"Missing: {', '.join(missing_kinds)}."
        ),
        requested_resource_kinds=missing_kinds,
        status="trainer_review",
    )
    # Trigger the full acquisition pipeline — downloads any cataloged holdings
    # missing source.txt, indexes them, drafts library cards, and searches
    # archive.org if still insufficient.
    result = escalate_for_passage(
        scripture_reference=bundle.scripture_reference,
        topic=bundle.topic or "",
        missing_kinds=missing_kinds,
    )
    # Return True only if new rows were actually indexed — tells the caller
    # to rebuild the bundle from the now-richer catalog.
    return any(idx.get("rows_added", 0) > 0 for idx in result.get("indexed", []))


def _catalog_records_for_worker(
    *,
    scripture_reference: str,
    worker_name: str,
    requested_needs: list[str],
    purpose: str,
) -> list[PassageResourceRecord]:
    """Delegate catalog lookups to the deterministic reference librarian."""
    return _catalog_lookup(
        scripture_reference=scripture_reference,
        worker_name=worker_name,
        requested_needs=requested_needs,
        purpose=purpose,
    )


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
