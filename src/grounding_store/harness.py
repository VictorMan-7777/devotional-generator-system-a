"""harness.py — Phase 007 CP1 out-of-band artifact validation harness.

Provides a standalone validation path for GroundingMap artifacts that is
entirely separate from generate_devotional(). Does not modify the pipeline,
orchestrator signature, or any existing validation rules.

The harness calls into existing validation logic (validate_exposition) using
a deterministic stub ExpositionSection that is guaranteed to pass the
non-grounding checks (EXPOSITION_WORD_COUNT, EXPOSITION_VOICE), then filters
the returned assessments to the EXPOSITION_GROUNDING_MAP check only.

No LLM calls. No network calls. No pipeline wiring.
"""
from __future__ import annotations

from typing import List

from src.grounding_store.store import GroundingMapStore
from src.models.devotional import ExpositionSection, SectionApprovalStatus
from src.models.validation import ValidatorAssessment
from src.validation.exposition import validate_exposition

# ---------------------------------------------------------------------------
# Deterministic stub — passes EXPOSITION_WORD_COUNT and EXPOSITION_VOICE,
# so validate_exposition() returns all three checks and we can filter cleanly.
# ---------------------------------------------------------------------------
_STUB_WORD_COUNT = 500
_STUB_TEXT = " ".join(["grace"] * _STUB_WORD_COUNT)

_GROUNDING_CHECK_ID = "EXPOSITION_GROUNDING_MAP"


def validate_grounding_map_artifact(
    grounding_map_id: str,
    store: GroundingMapStore,
) -> List[ValidatorAssessment]:
    """Load a GroundingMap and run the grounding-specific validation checks.

    This executes the checks that are normally skipped when
    ``grounding_map=None`` is passed to ``validate_daily_devotional()``,
    without modifying the pipeline or orchestrator signature.

    Calls into the existing ``validate_exposition()`` entry point; does not
    reimplement any validation rules.

    Args:
        grounding_map_id: The id of the GroundingMap artifact to validate.
        store: The GroundingMapStore instance to load from.

    Returns:
        List[ValidatorAssessment] containing only the
        ``EXPOSITION_GROUNDING_MAP`` assessment.

    Raises:
        KeyError: if ``grounding_map_id`` is not present in the store.
        pydantic.ValidationError: if the stored artifact fails Pydantic
            model validation (e.g. corrupted or incomplete JSON).
    """
    # Load artifact — raises KeyError if missing, ValidationError if corrupt.
    loaded = store.load(grounding_map_id)

    stub_section = ExpositionSection(
        text=_STUB_TEXT,
        word_count=_STUB_WORD_COUNT,
        grounding_map_id=grounding_map_id,
        approval_status=SectionApprovalStatus.PENDING,
    )

    assessments = validate_exposition(stub_section, grounding_map=loaded)

    return [a for a in assessments if a.check_id == _GROUNDING_CHECK_ID]
