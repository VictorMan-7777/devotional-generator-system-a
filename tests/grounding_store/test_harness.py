"""Unit tests for src/grounding_store/harness.py — validate_grounding_map_artifact.

Required behaviours:
  4) valid stored map → harness returns assessments list
  5) missing id → KeyError
  6) invalid map (manually corrupted JSON) → Pydantic ValidationError surfaces
  7) harness does NOT mutate store
"""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.grounding_store.harness import validate_grounding_map_artifact
from src.grounding_store.store import GroundingMapStore
from src.interfaces.rag import RetrievedExcerpt
from src.models.artifacts import GroundingMap
from src.models.validation import ValidatorAssessment
from src.rag.grounding import GroundingMapBuilder


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_excerpt(text: str) -> RetrievedExcerpt:
    return RetrievedExcerpt(
        text=text,
        source_title="Matthew Henry's Commentary",
        author="Matthew Henry",
        source_type="commentary",
    )


def _four_paragraph_excerpts() -> dict:
    return {
        1: [_make_excerpt("Declaration text.")],
        2: [_make_excerpt("Context text A."), _make_excerpt("Context text B.")],
        3: [_make_excerpt("Theological text.")],
        4: [_make_excerpt("Bridge text.")],
    }


@pytest.fixture
def sample_map() -> GroundingMap:
    return GroundingMapBuilder().build("expo-harness-001", _four_paragraph_excerpts())


@pytest.fixture
def store(tmp_path: Path) -> GroundingMapStore:
    return GroundingMapStore(tmp_path)


# ---------------------------------------------------------------------------
# 4. valid stored map → harness returns assessments list
# ---------------------------------------------------------------------------


class TestValidStoredMap:
    def test_returns_list(self, store: GroundingMapStore, sample_map: GroundingMap):
        store.save(sample_map)
        result = validate_grounding_map_artifact(sample_map.id, store)
        assert isinstance(result, list)

    def test_returns_validator_assessments(self, store: GroundingMapStore, sample_map: GroundingMap):
        store.save(sample_map)
        result = validate_grounding_map_artifact(sample_map.id, store)
        assert len(result) > 0
        assert all(isinstance(a, ValidatorAssessment) for a in result)

    def test_contains_grounding_map_check(self, store: GroundingMapStore, sample_map: GroundingMap):
        store.save(sample_map)
        result = validate_grounding_map_artifact(sample_map.id, store)
        check_ids = [a.check_id for a in result]
        assert "EXPOSITION_GROUNDING_MAP" in check_ids

    def test_valid_map_assessment_passes(self, store: GroundingMapStore, sample_map: GroundingMap):
        store.save(sample_map)
        result = validate_grounding_map_artifact(sample_map.id, store)
        gm_assessment = next(a for a in result if a.check_id == "EXPOSITION_GROUNDING_MAP")
        assert gm_assessment.result == "pass"

    def test_only_grounding_check_returned(self, store: GroundingMapStore, sample_map: GroundingMap):
        """Harness returns only grounding-related assessments, not word_count or voice."""
        store.save(sample_map)
        result = validate_grounding_map_artifact(sample_map.id, store)
        for assessment in result:
            assert assessment.check_id == "EXPOSITION_GROUNDING_MAP"


# ---------------------------------------------------------------------------
# 5. missing id → KeyError
# ---------------------------------------------------------------------------


class TestMissingId:
    def test_missing_id_raises_key_error(self, store: GroundingMapStore):
        with pytest.raises(KeyError):
            validate_grounding_map_artifact("nonexistent-gm-id", store)

    def test_error_message_contains_id(self, store: GroundingMapStore):
        missing_id = "gm_deadbeef"
        with pytest.raises(KeyError, match=missing_id):
            validate_grounding_map_artifact(missing_id, store)


# ---------------------------------------------------------------------------
# 6. invalid map (corrupted JSON) → Pydantic ValidationError surfaces
# ---------------------------------------------------------------------------


class TestCorruptedMap:
    def test_corrupted_json_raises_validation_error(
        self, store: GroundingMapStore, sample_map: GroundingMap
    ):
        """Corrupt the stored file so entries=[] fails the GroundingMap validator."""
        store.save(sample_map)
        # Overwrite with JSON that passes json.loads but fails Pydantic validation
        # (GroundingMap requires exactly 4 entries; 0 entries → field_validator raises)
        corrupt = '{"id": "gm_corrupt", "exposition_id": "x", "entries": []}'
        (store._dir / f"{sample_map.id}.json").write_text(corrupt, encoding="utf-8")
        with pytest.raises(ValidationError):
            validate_grounding_map_artifact(sample_map.id, store)


# ---------------------------------------------------------------------------
# 7. harness does NOT mutate store
# ---------------------------------------------------------------------------


class TestHarnessDoesNotMutateStore:
    def test_store_state_unchanged_after_harness(
        self, store: GroundingMapStore, sample_map: GroundingMap
    ):
        store.save(sample_map)
        data_before = store.load(sample_map.id).model_dump()

        validate_grounding_map_artifact(sample_map.id, store)

        data_after = store.load(sample_map.id).model_dump()
        assert data_before == data_after

    def test_no_extra_files_created_in_store(
        self, store: GroundingMapStore, sample_map: GroundingMap
    ):
        store.save(sample_map)
        files_before = set(store._dir.iterdir())

        validate_grounding_map_artifact(sample_map.id, store)

        files_after = set(store._dir.iterdir())
        assert files_before == files_after
