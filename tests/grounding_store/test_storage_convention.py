"""Unit tests for Phase 007 canonical storage convention in GroundingMapStore.

Required behaviours:
   8) DEFAULT_ROOT path resolves to canonical structure
      (data/artifacts/grounding_maps within the project)
   9) save without injected root writes to canonical path
  10) directory auto-created on first construction (mkdir parents=True)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.grounding_store.store import GroundingMapStore, _DEFAULT_ROOT
from src.interfaces.rag import RetrievedExcerpt
from src.models.artifacts import GroundingMap
from src.rag.grounding import GroundingMapBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_excerpt(text: str) -> RetrievedExcerpt:
    return RetrievedExcerpt(
        text=text,
        source_title="Source",
        author="Author",
        source_type="commentary",
    )


@pytest.fixture
def sample_map() -> GroundingMap:
    return GroundingMapBuilder().build(
        "expo-conv-001",
        {
            1: [_make_excerpt("Para 1.")],
            2: [_make_excerpt("Para 2.")],
            3: [_make_excerpt("Para 3.")],
            4: [_make_excerpt("Para 4.")],
        },
    )


# ---------------------------------------------------------------------------
# 8. DEFAULT_ROOT path matches canonical structure
# ---------------------------------------------------------------------------


class TestDefaultRootStructure:
    def test_default_root_ends_with_grounding_maps(self):
        assert _DEFAULT_ROOT.parts[-1] == "grounding_maps"

    def test_default_root_contains_artifacts(self):
        assert _DEFAULT_ROOT.parts[-2] == "artifacts"

    def test_default_root_contains_data(self):
        assert _DEFAULT_ROOT.parts[-3] == "data"

    def test_default_root_is_absolute(self):
        """Path must be anchored via __file__, not CWD-relative."""
        assert _DEFAULT_ROOT.is_absolute()

    def test_default_root_is_path_instance(self):
        assert isinstance(_DEFAULT_ROOT, Path)

    def test_canonical_tail_matches_exactly(self):
        """Trailing three path segments match: data/artifacts/grounding_maps."""
        tail = Path(*_DEFAULT_ROOT.parts[-3:])
        assert tail == Path("data") / "artifacts" / "grounding_maps"


# ---------------------------------------------------------------------------
# 9. save without injected root uses canonical path
# ---------------------------------------------------------------------------


class TestCanonicalPathUsed:
    def test_store_dir_equals_injected_root(self, tmp_path: Path):
        """When tmp_path is injected, _dir resolves to tmp_path directly."""
        store = GroundingMapStore(tmp_path)
        assert store._dir == tmp_path

    def test_default_store_dir_equals_default_root(self):
        """Default constructor sets _dir to _DEFAULT_ROOT.

        Directly instantiate with the module-level default and verify _dir.
        (Monkeypatching _DEFAULT_ROOT cannot affect the already-bound default
        argument value in __init__, so we test the actual production path.)
        """
        store = GroundingMapStore()
        assert store._dir == _DEFAULT_ROOT

    def test_saved_file_is_in_root_dir(self, tmp_path: Path, sample_map: GroundingMap):
        """File is placed directly in root_dir, not in a subdirectory."""
        store = GroundingMapStore(tmp_path)
        store.save(sample_map)
        expected = tmp_path / f"{sample_map.id}.json"
        assert expected.exists()

    def test_no_extra_subdirectory_created(self, tmp_path: Path, sample_map: GroundingMap):
        """Files must be at <root>/<id>.json — no grounding-maps/ subdirectory."""
        store = GroundingMapStore(tmp_path)
        store.save(sample_map)
        # Only one item in the dir: the <id>.json file itself.
        children = list(tmp_path.iterdir())
        assert len(children) == 1
        assert children[0].name == f"{sample_map.id}.json"


# ---------------------------------------------------------------------------
# 10. directory auto-created on first construction
# ---------------------------------------------------------------------------


class TestDirectoryAutoCreated:
    def test_nested_path_created_on_init(self, tmp_path: Path):
        nested = tmp_path / "deep" / "nested" / "path"
        assert not nested.exists()
        GroundingMapStore(nested)
        assert nested.is_dir()

    def test_existing_dir_does_not_raise(self, tmp_path: Path):
        """exist_ok=True: constructing twice must not raise."""
        GroundingMapStore(tmp_path)
        GroundingMapStore(tmp_path)  # should not raise

    def test_can_save_immediately_after_init(self, tmp_path: Path, sample_map: GroundingMap):
        nested = tmp_path / "auto_created"
        store = GroundingMapStore(nested)
        store.save(sample_map)  # must succeed; directory already created in __init__
        assert store.exists(sample_map.id)
