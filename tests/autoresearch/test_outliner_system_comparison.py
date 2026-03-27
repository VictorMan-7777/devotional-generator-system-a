from __future__ import annotations

from src.autoresearch.reasoning_outliner_core import build_reasoning_editorial_artifact
from src.models.pipeline import PassageResourceBundle


def test_build_reasoning_editorial_artifact_is_independent_of_editorial_helpers() -> None:
    artifact = build_reasoning_editorial_artifact(
        topic="Ruth 1",
        source_reference="Ruth 1",
        num_days=2,
        num_weeks=1,
        day_inputs=[
            {
                "scripture_reference": "Ruth 1:1-5",
                "study_window_reference": "Ruth 1:1-5",
                "key_verse_reference": "Ruth 1:4-5",
                "scripture_text": "In the days when the judges ruled there was a famine in the land.",
            },
            {
                "scripture_reference": "Ruth 1:6-10",
                "study_window_reference": "Ruth 1:6-10",
                "key_verse_reference": "Ruth 1:8-9",
                "scripture_text": "Then she arose with her daughters-in-law that she might return from the land of Moab.",
            },
        ],
        passage_resources=PassageResourceBundle(
            topic="Ruth 1",
            scripture_reference="Ruth 1",
            prepared_at_utc="2026-03-16T00:00:00Z",
        ),
    )
    assert artifact.num_days == 2
    assert artifact.day_briefs[0].key_verse_reference == "Ruth 1:4-5"
    assert artifact.day_briefs[0].focus_clause
    assert artifact.week_plans
