from __future__ import annotations

from src.models.devotional import DailyDevotional
from src.generation.generators import MockSectionGenerator
from src.validation.book_quality import validate_devotional_book
from tests.fixtures.sample_devotional import SAMPLE_BOOK


def _clone_day(day: DailyDevotional, *, day_number: int | None = None) -> DailyDevotional:
    clone = day.model_copy(deep=True)
    if day_number is not None:
        clone.day_number = day_number
        clone.day_focus = f"Day {day_number} theme - grace in the ordinary"
    return clone


def test_day_coherence_failure_is_reported() -> None:
    book = SAMPLE_BOOK.model_copy(deep=True)
    day = _clone_day(book.days[0])
    day.be_still.prompts = [
        "Sit quietly for two minutes.",
        "What are you feeling right now?",
        "Keep breathing slowly.",
    ]
    day.action_steps.items = [
        "Drink more water this afternoon.",
        "Take a short walk before dinner.",
    ]
    day.prayer.text = (
        "Father, give calm and comfort today. Help with rest and peace in all things. "
        "Let this be a steady day of quiet. Amen. "
    ) * 4
    book.days[0] = day

    findings = validate_devotional_book(book)

    assert any(
        finding.check_id == "BOOK_DAY_COHERENCE"
        and finding.day_numbers == [1]
        for finding in findings
    )


def test_adjacent_day_progression_failure_is_reported() -> None:
    book = SAMPLE_BOOK.model_copy(deep=True)
    book.days[1] = _clone_day(book.days[0], day_number=2)

    findings = validate_devotional_book(book)

    assert any(
        finding.check_id == "BOOK_DAY_PROGRESS"
        and finding.day_numbers == [1, 2]
        for finding in findings
    )


def test_week_transition_failure_is_reported() -> None:
    book = SAMPLE_BOOK.model_copy(deep=True)
    book.input.num_days = 8
    extra_day = _clone_day(book.days[3], day_number=8)
    book.days.append(extra_day)
    book.days[4] = _clone_day(book.days[3], day_number=5)

    findings = validate_devotional_book(book)

    assert any(
        finding.check_id == "BOOK_WEEK_TRANSITION"
        for finding in findings
    )


def test_theological_boundary_flattening_is_reported() -> None:
    book = SAMPLE_BOOK.model_copy(deep=True)
    day = _clone_day(book.days[0])
    day.scripture.text = "The wrath of God is revealed against all ungodliness and unrighteousness."
    day.exposition.text = (
        "This passage invites calm, rest, and gratitude without any call to repentance or truth. "
        "It is mainly about quiet comfort in every season. "
    ) * 8
    day.prayer.text = (
        "Father, give peace, comfort, and rest. Let there be calm, gratitude, and kindness today. Amen. "
    ) * 5
    day.action_steps.items = [
        "Protect ten minutes of calm this afternoon.",
        "Offer one kind gesture today.",
    ]
    book.days[0] = day

    findings = validate_devotional_book(book)

    assert any(
        finding.reason_code == "THEOLOGICAL_BOUNDARY_FLATTENING"
        and finding.day_numbers == [1]
        for finding in findings
    )


def test_coherent_book_passes_quality_gate() -> None:
    book = SAMPLE_BOOK.model_copy(deep=True)
    generator = MockSectionGenerator()
    for idx in range(len(book.days)):
        book.days[idx] = generator.generate_day(
            "grace",
            idx + 1,
            scripture_reference=f"Romans 1:{idx + 1}",
        )
    findings = validate_devotional_book(book)
    assert findings == []
