"""store.py — Phase 009 PrayerTraceMapStore.

Local-only deterministic persistence for PrayerTraceMap artifacts.
Each PrayerTraceMap is serialised as JSON directly under root_dir:
  <root_dir>/<id>.json

Canonical default: <project_root>/data/artifacts/prayer_trace_maps/<id>.json

Mirrors GroundingMapStore (Phase 006/007) in structure and semantics.
No encryption. No network. No LLM calls. No embeddings.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.models.artifacts import PrayerTraceMap

# Anchored canonical default — does not depend on CWD.
# Canonical path: <project_root>/data/artifacts/prayer_trace_maps/
# __file__ is src/prayer_trace_store/store.py → parent×3 is project root.
_DEFAULT_ROOT: Path = (
    Path(__file__).parent.parent.parent / "data" / "artifacts" / "prayer_trace_maps"
)


class PrayerTraceMapStore:
    """Local-only deterministic store for PrayerTraceMap artifacts.

    Each map is persisted as JSON directly under root_dir:
      <root_dir>/<id>.json

    The canonical default is:
      <project_root>/data/artifacts/prayer_trace_maps/<id>.json

    Serialisation uses ``json.dumps(sort_keys=True)`` for determinism.

    Args:
        root_dir: Directory where JSON files are stored directly.
                  Created (with parents) on construction if absent.
                  Inject ``tmp_path`` in tests.

    Class Attributes:
        DEFAULT_ROOT: The canonical root directory.  Exposed as a class
                      attribute so callers can read it at runtime (e.g. for
                      monkeypatching in tests) rather than at import time.
    """

    DEFAULT_ROOT: Path = _DEFAULT_ROOT

    def __init__(self, root_dir: Path = _DEFAULT_ROOT) -> None:
        self._dir = root_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _path(self, trace_map_id: str) -> Path:
        return self._dir / f"{trace_map_id}.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, trace_map: PrayerTraceMap) -> None:
        """Persist trace_map to <root_dir>/<id>.json.

        Overwrites any existing file for the same id.
        Output is deterministic: identical input always produces identical bytes.
        """
        data = trace_map.model_dump(mode="json")
        text = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)
        self._path(trace_map.id).write_text(text, encoding="utf-8")

    def load(self, trace_map_id: str) -> PrayerTraceMap:
        """Load and return a PrayerTraceMap from disk.

        Args:
            trace_map_id: The ``id`` field of the PrayerTraceMap to retrieve.

        Returns:
            The deserialised PrayerTraceMap.

        Raises:
            KeyError: if no map file exists for the given id.
        """
        p = self._path(trace_map_id)
        if not p.exists():
            raise KeyError(
                f"PrayerTraceMapStore: no artifact found for id={trace_map_id!r}"
            )
        data = json.loads(p.read_text(encoding="utf-8"))
        return PrayerTraceMap.model_validate(data)

    def exists(self, trace_map_id: str) -> bool:
        """Return True if a map file exists for the given id."""
        return self._path(trace_map_id).exists()
