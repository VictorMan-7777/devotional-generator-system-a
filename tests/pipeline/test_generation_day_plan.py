from __future__ import annotations

from src.models.pipeline import PassageResourceBundle
from src.api.generation_pipeline import generate_devotional
from src.generation.generators import MockSectionGenerator
from src.models.devotional import OutputMode


def test_generate_devotional_uses_day_plan_scripture_reference() -> None:
    day_plan = [
        {"topic": "Holiness Day 1", "scripture_reference": "1 Samuel 2:2"},
        {"topic": "Holiness Day 2", "scripture_reference": "Isaiah 6:3"},
    ]
    result = generate_devotional(
        topic="fallback-topic",
        num_days=2,
        scripture_reference=None,
        day_plan=day_plan,
        output_mode=OutputMode.PERSONAL,
        generator=MockSectionGenerator(),
    )

    assert result.book.days[0].scripture.reference.startswith("1 Samuel 2:2")
    assert result.book.days[1].scripture.reference.startswith("Isaiah 6:3")
    assert result.editorial_build.day_briefs[0].scripture_reference.startswith("1 Samuel 2:2")
    assert result.editorial_build.day_briefs[1].scripture_reference.startswith("Isaiah 6:3")
    assert result.editorial_build.day_briefs[0].key_verse_reference.startswith("1 Samuel 2:2")
    assert result.editorial_build.day_plan[0].study_window_reference.startswith("1 Samuel 2:2")
    assert result.editorial_build.day_briefs[0].genre
    assert result.editorial_build.day_briefs[0].application_lane
    assert result.editorial_build.week_count == 1


def test_generate_devotional_auto_plans_from_scripture_reference() -> None:
    result = generate_devotional(
        topic="Creation",
        num_days=12,
        scripture_reference="Genesis 1 & 2",
        day_plan=None,
        output_mode=OutputMode.PERSONAL,
        generator=MockSectionGenerator(),
    )

    got = [d.scripture.reference.split(" (Day ")[0] for d in result.book.days]
    assert len(got) == 12
    assert got[0].startswith("Genesis 1:")
    tail = got[-1].split()[-1]
    assert int(tail.split("-")[-1].split(":")[-1]) <= 25
    for ref in got:
        verse_part = ref.split()[-1]
        if "-" in verse_part:
            left, right = verse_part.split("-", maxsplit=1)
            start = int(left.split(":")[-1])
            end = int(right.split(":")[-1])
            assert (end - start + 1) <= 2
    assert len(result.editorial_build.day_plan) == 12
    assert result.editorial_build.day_briefs[0].day_title.startswith("Genesis 1:")
    assert result.editorial_build.day_briefs[0].study_window_reference
    assert result.editorial_build.day_briefs[0].key_verse_reference == result.editorial_build.day_briefs[0].scripture_reference
    assert result.editorial_build.day_briefs[0].study_window_reference != result.editorial_build.day_briefs[0].scripture_reference
    assert result.editorial_build.week_count == 2
    assert result.editorial_build.day_plan[0].scripture_reference.split(" (Day ")[0] == got[0]
    assert result.editorial_build.day_plan[0].study_window_reference


def test_generate_devotional_auto_plans_from_topic_when_topic_is_scripture_range() -> None:
    result = generate_devotional(
        topic="Genesis 1 & 2",
        num_days=12,
        scripture_reference=None,
        day_plan=None,
        output_mode=OutputMode.PERSONAL,
        generator=MockSectionGenerator(),
    )
    assert len(result.book.days) == 12
    got = [d.scripture.reference.split(" (Day ")[0] for d in result.book.days]
    assert got[0].startswith("Genesis 1:")
    tail = got[-1].split()[-1]
    assert int(tail.split("-")[-1].split(":")[-1]) <= 25
    assert result.editorial_build.source_reference is None
    assert result.editorial_build.week_plans[0].days == [1, 2, 3, 4, 5, 6, 7]
    assert result.editorial_build.week_plans[1].days == [8, 9, 10, 11, 12]


def test_generate_devotional_strict_mode_fails_when_topic_has_no_scripture_range() -> None:
    try:
        generate_devotional(
            topic="grace",
            num_days=12,
            scripture_reference=None,
            day_plan=None,
            output_mode=OutputMode.PERSONAL,
            generator=MockSectionGenerator(),
            require_planned_scripture=True,
        )
    except ValueError as exc:
        assert "Only 0 scriptures found for topic 'grace'" in str(exc)
    else:
        raise AssertionError("Expected ValueError when strict planning has no scripture source")


def test_generate_devotional_strict_mode_fails_when_day_plan_too_short() -> None:
    try:
        generate_devotional(
            topic="Genesis 1 & 2",
            num_days=3,
            scripture_reference=None,
            day_plan=[{"topic": "a", "scripture_reference": "Genesis 1:1-2"}],
            output_mode=OutputMode.PERSONAL,
            generator=MockSectionGenerator(),
            require_planned_scripture=True,
        )
    except ValueError as exc:
        assert "Only 1 scriptures found for topic 'Genesis 1 & 2', 3 needed." in str(exc)
    else:
        raise AssertionError("Expected ValueError for short day_plan in strict mode")


def test_generate_devotional_emits_checkpoint_stages() -> None:
    stages: list[str] = []

    def checkpoint(stage: str, payload: dict) -> None:
        stages.append(stage)

    result = generate_devotional(
        topic="Creation",
        num_days=3,
        scripture_reference="Genesis 1:1-10",
        output_mode=OutputMode.PERSONAL,
        generator=MockSectionGenerator(),
        checkpoint_callback=checkpoint,
    )

    assert result.book.days
    assert stages[0] == "outline_ready"
    assert stages.count("day_complete") == 3
    assert stages.count("day_unification") == 3
    assert "week_unification" in stages
    assert stages[-1] == "book_unification"


def test_generate_devotional_prepares_shared_passage_resources() -> None:
    class CaptureGenerator(MockSectionGenerator):
        seen_resources: list[PassageResourceBundle | None] = []

        def build_editorial_brief(
            self,
            topic: str,
            day_number: int,
            scripture_reference: str | None = None,
            passage_resources: PassageResourceBundle | None = None,
        ):
            self.seen_resources.append(passage_resources)
            return super().build_editorial_brief(
                topic,
                day_number,
                scripture_reference=scripture_reference,
                passage_resources=passage_resources,
            )

    generator = CaptureGenerator()
    result = generate_devotional(
        topic="Luke 15",
        num_days=2,
        scripture_reference="Luke 15",
        output_mode=OutputMode.PUBLISH_READY,
        generator=generator,
    )

    assert result.editorial_build.passage_resources is not None
    assert result.editorial_build.passage_resources.scripture_reference == "Luke 15"
    assert generator.seen_resources
    assert all(item is not None for item in generator.seen_resources)
