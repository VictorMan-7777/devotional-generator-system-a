"""store.py — Phase 006/007 GroundingMapStore + resolve_grounding_map.

Local-only deterministic persistence for GroundingMap artifacts.
Each GroundingMap is serialised as JSON directly under root_dir:
  <root_dir>/<id>.json

Canonical default: <project_root>/data/artifacts/grounding_maps/<id>.json
(Phase 007 CP1: DEFAULT_ROOT anchored via __file__; _SUBDIR removed.)

Serialisation is deterministic (sorted keys). No encryption. No network.
No LLM calls. No embeddings.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.models.artifacts import GroundingMap
from src.models.devotional import ExpositionSection

# Anchored canonical default — does not depend on CWD.
# Canonical path: <project_root>/data/artifacts/grounding_maps/
# __file__ is src/grounding_store/store.py → parent×3 is project root.
_DEFAULT_ROOT: Path = (
    Path(__file__).parent.parent.parent / "data" / "artifacts" / "grounding_maps"
)


class GroundingMapStore:
    """Local-only deterministic store for GroundingMap artifacts.

    Each map is persisted as JSON directly under root_dir:
      <root_dir>/<id>.json

    The canonical default is:
      <project_root>/data/artifacts/grounding_maps/<id>.json

    Serialisation uses ``json.dumps(sort_keys=True)`` for determinism.

    Args:
        root_dir: Directory where JSON files are stored directly.
                  Created (with parents) on construction if absent.
                  Inject ``tmp_path`` in tests.
    """

    def __init__(self, root_dir: Path = _DEFAULT_ROOT) -> None:
        self._dir = root_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _path(self, grounding_map_id: str) -> Path:
        return self._dir / f"{grounding_map_id}.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, grounding_map: GroundingMap) -> None:
        """Persist grounding_map to <root_dir>/<id>.json.

        Overwrites any existing file for the same id.
        Output is deterministic: identical input always produces identical bytes.
        """
        data = grounding_map.model_dump(mode="json")
        text = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)
        self._path(grounding_map.id).write_text(text, encoding="utf-8")

    def load(self, grounding_map_id: str) -> GroundingMap:
        """Load and return a GroundingMap from disk.

        Args:
            grounding_map_id: The ``id`` field of the GroundingMap to retrieve.

        Returns:
            The deserialised GroundingMap.

        Raises:
            KeyError: if no map file exists for the given id.
        """
        p = self._path(grounding_map_id)
        if not p.exists():
            raise KeyError(
                f"GroundingMapStore: no artifact found for id={grounding_map_id!r}"
            )
        data = json.loads(p.read_text(encoding="utf-8"))
        return GroundingMap.model_validate(data)

    def exists(self, grounding_map_id: str) -> bool:
        """Return True if a map file exists for the given id."""
        return self._path(grounding_map_id).exists()


# ---------------------------------------------------------------------------
# Resolver helper
# ---------------------------------------------------------------------------


def resolve_grounding_map(
    exposition_section: ExpositionSection,
    store: GroundingMapStore,
) -> Optional[GroundingMap]:
    """Resolve a GroundingMap for an ExpositionSection.

    Returns:
        ``None`` if ``exposition_section.grounding_map_id`` is falsy (e.g. the
        empty string ``""`` used as a placeholder).
        The ``GroundingMap`` if found in the store.

    Raises:
        KeyError: if ``grounding_map_id`` is non-falsy but the artifact is not
            present in the store.  This prevents silent skip when an id exists
            but the artifact was never saved.
    """
    gm_id = exposition_section.grounding_map_id
    if not gm_id:
        return None
    return store.load(gm_id)
