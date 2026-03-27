from __future__ import annotations

from src.scripture.planner import (
    plan_scripture_day_references,
    select_daily_key_verses_reference,
    suggest_study_window_size,
)
from src.scripture.retrieval import FailureMode, ScriptureFailureAlert, ScriptureResult


class _FakeRetriever:
    def __init__(self, chapter_sizes: dict[int, int]) -> None:
        self._chapter_sizes = chapter_sizes

    def retrieve(self, reference: str, translation: str = "NASB", operator_import=None):
        book_and_ch, verse_str = reference.rsplit(":", maxsplit=1)
        chapter = int(book_and_ch.split()[-1])
        verse = int(verse_str)
        if verse <= self._chapter_sizes.get(chapter, 0):
            return ScriptureResult(
                reference=reference,
                text=f"text {reference}",
                translation=translation,
                retrieval_source="bolls_life",
                verification_status="verified",
            )
        return ScriptureFailureAlert(
            reference=reference,
            translation=translation,
            failure_mode=FailureMode.ALL_SOURCES_EXHAUSTED,
            message="missing",
            attempted_sources=["bolls_life"],
        )


def test_plan_scripture_day_references_splits_chapter_range_to_num_days() -> None:
    refs = plan_scripture_day_references(
        reference="Genesis 1 & 2",
        num_days=12,
        max_verses_per_day=5,
        retriever=_FakeRetriever({1: 31, 2: 25}),
    )
    assert len(refs) == 12
    assert refs[0].startswith("Genesis 1:1-")
    tail = refs[-1].split()[-1]
    assert int(tail.split("-")[-1].split(":")[-1]) == 25
    for ref in refs:
        verse_part = ref.split()[-1]
        if "-" in verse_part:
            left, right = verse_part.split("-", maxsplit=1)
            start = int(left.split(":")[-1])
            end = int(right.split(":")[-1])
            assert (end - start + 1) <= 5
        else:
            assert ":" in verse_part


def test_plan_scripture_day_references_rejects_overflow_vs_day_limit() -> None:
    refs = plan_scripture_day_references(
        reference="Genesis 1 & 2",
        num_days=10,
        max_verses_per_day=5,
        retriever=_FakeRetriever({1: 31, 2: 25}),
    )
    assert len(refs) == 10
    for ref in refs:
        verse_part = ref.split()[-1]
        if "-" in verse_part:
            left, right = verse_part.split("-", maxsplit=1)
            start = int(left.split(":")[-1])
            end = int(right.split(":")[-1])
            assert (end - start + 1) <= 5


def test_plan_scripture_day_references_supports_genesis_book_level_6_day() -> None:
    refs = plan_scripture_day_references(
        reference="Genesis 1",
        num_days=6,
        max_verses_per_day=5,
        retriever=_FakeRetriever({1: 31}),
    )
    assert len(refs) == 6
    assert refs[0].startswith("Genesis 1:")
    assert refs[-1].startswith("Genesis 1:")


def test_plan_scripture_day_references_uses_curated_exodus_19_20_boundaries() -> None:
    refs = plan_scripture_day_references(
        reference="Exodus 19-20",
        num_days=12,
        retriever=_FakeRetriever({19: 25, 20: 26}),
    )
    assert refs == [
        "Exodus 19:1-4",
        "Exodus 19:5-8",
        "Exodus 19:9-13",
        "Exodus 19:14-19",
        "Exodus 19:20-25",
        "Exodus 20:1-3",
        "Exodus 20:4-6",
        "Exodus 20:7-11",
        "Exodus 20:12-14",
        "Exodus 20:15-17",
        "Exodus 20:18-21",
        "Exodus 20:22-26",
    ]


def test_plan_scripture_day_references_uses_curated_proverbs_1_2_boundaries() -> None:
    refs = plan_scripture_day_references(
        reference="Proverbs 1-2",
        num_days=12,
        retriever=_FakeRetriever({1: 33, 2: 22}),
    )
    assert refs[5] == "Proverbs 1:29-33"
    assert refs[6] == "Proverbs 2:1-5"
    assert refs[-1] == "Proverbs 2:20-22"


def test_plan_scripture_day_references_uses_curated_acts_9_boundaries() -> None:
    refs = plan_scripture_day_references(
        reference="Acts 9",
        num_days=12,
        retriever=_FakeRetriever({9: 43}),
    )
    assert refs[1] == "Acts 9:4-6"
    assert refs[8] == "Acts 9:26-31"
    assert refs[-1] == "Acts 9:40-43"


def test_select_daily_key_verses_reference_narrows_to_center_pair() -> None:
    assert select_daily_key_verses_reference(reference="Habakkuk 1:5-9", max_key_verses=2) == "Habakkuk 1:7-8"


def test_suggest_study_window_size_uses_passage_density() -> None:
    assert suggest_study_window_size(
        reference="Genesis 1 & 2",
        num_days=12,
        retriever=_FakeRetriever({1: 31, 2: 25}),
    ) == 5
    assert suggest_study_window_size(
        reference="Genesis 1",
        num_days=6,
        retriever=_FakeRetriever({1: 31}),
    ) == 5
