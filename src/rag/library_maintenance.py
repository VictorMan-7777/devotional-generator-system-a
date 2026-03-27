from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.rag.cuttings_inventory import inventory_cutting_sources, synchronize_cuttings_with_library
from src.rag.library_catalog import load_library_catalog
from src.rag.library_requests import list_resource_acquisition_requests


@dataclass(frozen=True)
class LibraryTask:
    owner: str
    task_type: str
    priority: int
    title: str
    detail: str


def build_library_maintenance_queue(
    catalog_path: Path | None = None,
) -> list[LibraryTask]:
    synchronize_cuttings_with_library()
    catalog = load_library_catalog(catalog_path) if catalog_path else load_library_catalog()
    known_titles = {entry.title for entry in catalog}
    tasks: list[LibraryTask] = []

    for source in inventory_cutting_sources():
        if source.source_title in known_titles:
            continue
        tasks.append(
            LibraryTask(
                owner="acquisition_librarian",
                task_type="acquire_parent_resource",
                priority=100,
                title=f"Acquire parent resource: {source.source_title}",
                detail=(
                    f"Current library only has {source.source_kind.replace('_', ' ')} from this source. "
                    f"Acquire the full resource by {source.author or 'unknown author'} and create a shelf-ready card. "
                    f"Observed cuttings: {source.cutting_count}."
                ),
            )
        )

    for entry in catalog:
        if entry.acquisition_status == "planned":
            tasks.append(
                LibraryTask(
                    owner="acquisition_librarian",
                    task_type="planned_acquisition",
                    priority=max(1, 100 - entry.preferred_order),
                    title=f"Acquire and catalog {entry.title}",
                    detail=(
                        f"Resource is still planned. Covered books: {', '.join(entry.covered_books) or 'n/a'}. "
                        f"Serves needs: {', '.join(entry.serves_needs) or 'n/a'}."
                    ),
                )
            )
        elif entry.acquisition_status in {"acquired", "cataloged"} and entry.catalog_status != "verified":
            tasks.append(
                LibraryTask(
                    owner="acquisition_librarian",
                    task_type="catalog_verification",
                    priority=max(1, 90 - entry.preferred_order),
                    title=f"Verify card catalog for {entry.title}",
                    detail="Resource exists but the card catalog is not yet verified as shelf-ready.",
                )
            )
        elif entry.catalog_status == "verified":
            tasks.append(
                LibraryTask(
                    owner="research_librarian",
                    task_type="resource_reading_notes",
                    priority=max(1, 20 - entry.preferred_order),
                    title=f"Read and annotate {entry.title}",
                    detail=(
                        "Lower-priority shelf reading after active worker needs are covered. "
                        "Use notes to learn what the volume actually contains and how it should be used."
                    ),
                )
            )
    for request in list_resource_acquisition_requests(status="requested"):
        tasks.append(
            LibraryTask(
                owner="acquisition_librarian",
                task_type="acquisition_request",
                priority=100,
                title=f"Fulfill acquisition request for {request.scripture_reference}",
                detail=(
                    f"Requested by {request.requested_by}. "
                    f"Needs: {', '.join(request.requested_resource_kinds) or 'n/a'}. "
                    f"Reason: {request.reason}"
                ),
            )
        )

    for request in list_resource_acquisition_requests(status="requested"):
        tasks.append(
            LibraryTask(
                owner="research_librarian",
                task_type="thin_library_followup",
                priority=90,
                title=f"Track thin library request for {request.scripture_reference}",
                detail=(
                    "Monitor whether catalog growth is needed for this passage family and "
                    "which future passages may face the same shortage."
                ),
            )
        )

    return sorted(tasks, key=lambda item: (-item.priority, item.owner, item.title))


def queue_as_jsonable(tasks: list[LibraryTask]) -> list[dict[str, object]]:
    return [
        {
            "owner": task.owner,
            "task_type": task.task_type,
            "priority": task.priority,
            "title": task.title,
            "detail": task.detail,
        }
        for task in tasks
    ]


def queue_json(catalog_path: Path | None = None) -> str:
    return json.dumps(queue_as_jsonable(build_library_maintenance_queue(catalog_path)), indent=2)
