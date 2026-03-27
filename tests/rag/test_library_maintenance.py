from __future__ import annotations

import json

from src.rag.library_maintenance import build_library_maintenance_queue, queue_json
from src.rag.cuttings_inventory import inventory_cutting_sources


def test_library_maintenance_queue_contains_acquisition_librarian_work() -> None:
    tasks = build_library_maintenance_queue()
    assert any(task.owner == "acquisition_librarian" for task in tasks)


def test_library_maintenance_queue_json_is_valid() -> None:
    payload = queue_json()
    data = json.loads(payload)
    assert isinstance(data, list)


def test_cuttings_inventory_finds_parent_sources() -> None:
    items = inventory_cutting_sources()
    titles = {item.source_title for item in items}
    assert "Matthew Henry's Commentary on the Whole Bible" in titles
    assert "Spurgeon's Sermons" in titles


def test_library_maintenance_queue_prioritizes_parent_resource_acquisition() -> None:
    tasks = build_library_maintenance_queue()
    assert any(task.task_type == "acquire_parent_resource" for task in tasks)
