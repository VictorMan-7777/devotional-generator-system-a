"""book_quality.py - deterministic pre-review book-level quality checks.

Validates whole-book composition quality before human review:
- intra-day coherence
- adjacent-day progression
- week transition
- theological boundary / passage-lane fidelity
"""
from __future__ import annotations

import re
from collections import Counter

from src.models.devotional import DailyDevotional, DevotionalBook
from src.models.validation import BookValidatorAssessment

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "before", "but", "by",
    "for", "from", "has", "have", "he", "her", "his", "in", "into", "is", "it",
    "its", "of", "on", "or", "our", "that", "the", "their", "them", "there",
    "this", "to", "today", "was", "we", "with", "you", "your", "day", "read",
    "passage", "scripture", "verse", "verses", "week",
}

_BOOK_NAMES = {
    "genesis", "exodus", "leviticus", "numbers", "deuteronomy", "joshua", "judges",
    "ruth", "samuel", "kings", "chronicles", "ezra", "nehemiah", "esther", "job",
    "psalm", "psalms", "proverbs", "ecclesiastes", "song", "isaiah", "jeremiah",
    "lamentations", "ezekiel", "daniel", "hosea", "joel", "amos", "obadiah", "jonah",
    "micah", "nahum", "habakkuk", "zephaniah", "haggai", "zechariah", "malachi",
    "matthew", "mark", "luke", "john", "acts", "romans", "corinthians", "galatians",
    "ephesians", "philippians", "colossians", "thessalonians", "timothy", "titus",
    "philemon", "hebrews", "james", "peter", "jude", "revelation",
}

_THEOLOGICAL_KEYWORDS = {
    "sin", "grace", "mercy", "faith", "hope", "love", "peace", "obedience",
    "repentance", "repent", "forgiveness", "holiness", "holy", "righteousness",
    "righteous", "truth", "trust", "gospel", "kingdom", "cross", "resurrection",
    "suffering", "suffer", "death", "life", "spirit", "lord", "christ", "jesus",
    "god", "father", "judgment", "judge", "wrath", "creation", "covenant",
    "redemption", "redeem", "worship", "humility", "patience", "justice",
}

_SEVERE_THEMES = {
    "sin", "repentance", "repent", "judgment", "judge", "wrath", "death",
    "cross", "crucified", "suffering", "suffer",
}

_COMFORT_THEMES = {
    "peace", "rest", "comfort", "gratitude", "kindness", "calm", "stillness",
}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")


def _editorial_week_number(day_number: int) -> int:
    return ((day_number - 1) // 7) + 1


def _tokens(text: str) -> list[str]:
    return [
        token.lower()
        for token in _WORD_RE.findall(str(text or ""))
        if token.lower() not in _STOPWORDS and token.lower() not in _BOOK_NAMES
    ]


def _anchor_tokens(day: DailyDevotional, topic: str) -> list[str]:
    ordered: list[str] = []
    for source in (day.day_focus or "", topic, day.scripture.reference, day.scripture.text):
        for token in _tokens(source):
            if token not in ordered:
                ordered.append(token)
    thematic = [token for token in ordered if token in _THEOLOGICAL_KEYWORDS]
    content = [token for token in ordered if token not in thematic]
    if thematic:
        return (thematic[:3] + content[:3])[:6]
    return ordered[:6]


def _section_tokens(day: DailyDevotional) -> dict[str, set[str]]:
    return {
        "exposition": set(_tokens(day.exposition.text)),
        "be_still": set(_tokens(" ".join(day.be_still.prompts))),
        "action_steps": set(_tokens(" ".join(day.action_steps.items))),
        "prayer": set(_tokens(day.prayer.text)),
    }


def _similarity(left: str, right: str) -> float:
    left_counts = Counter(_tokens(left))
    right_counts = Counter(_tokens(right))
    if not left_counts and not right_counts:
        return 1.0
    if not left_counts or not right_counts:
        return 0.0
    shared = sum(min(left_counts[token], right_counts[token]) for token in left_counts.keys() & right_counts.keys())
    total = max(sum(left_counts.values()), sum(right_counts.values()))
    return shared / total if total else 0.0


def _combined_day_text(day: DailyDevotional) -> str:
    return " ".join(
        [
            day.exposition.text,
            " ".join(day.be_still.prompts),
            " ".join(day.action_steps.items),
            day.prayer.text,
        ]
    )


def _day_coherence(day: DailyDevotional, topic: str) -> list[BookValidatorAssessment]:
    anchors = set(_anchor_tokens(day, topic))
    if not anchors:
        return []
    sections = _section_tokens(day)
    aligned_sections = [
        name for name, section_tokens in sections.items() if anchors & section_tokens
    ]
    if len(aligned_sections) >= 2:
        return []
    return [
        BookValidatorAssessment(
            check_id="BOOK_DAY_COHERENCE",
            result="fail",
            reason_code="DAY_COHERENCE_WEAK",
            explanation=(
                "The day's sections do not stay anchored to the same scripture/topic burden. "
                "At least three major sections should echo the same core focus before review."
            ),
            evidence=f"aligned_sections={aligned_sections} anchors={sorted(anchors)}",
            day_numbers=[day.day_number],
        )
    ]


def _day_progression(book: DevotionalBook) -> list[BookValidatorAssessment]:
    findings: list[BookValidatorAssessment] = []
    for previous, current in zip(book.days, book.days[1:]):
        combined_similarity = _similarity(_combined_day_text(previous), _combined_day_text(current))
        actions_same = previous.action_steps.items == current.action_steps.items
        prompts_same = previous.be_still.prompts == current.be_still.prompts
        if combined_similarity > 0.90 or (actions_same and prompts_same):
            findings.append(
                BookValidatorAssessment(
                    check_id="BOOK_DAY_PROGRESS",
                    result="fail",
                    reason_code="DAY_PROGRESS_STALLED",
                    explanation=(
                        "Adjacent days are too similar. The devotional should progress from day to day "
                        "instead of repeating the same reflection pattern."
                    ),
                    evidence=f"similarity={combined_similarity:.2f}",
                    day_numbers=[previous.day_number, current.day_number],
                )
            )
    return findings


def _week_transition(book: DevotionalBook, topic: str) -> list[BookValidatorAssessment]:
    if len(book.days) < 8:
        return []
    boundary_pair: tuple[DailyDevotional, DailyDevotional] | None = None
    day_by_number = {day.day_number: day for day in book.days}
    max_day = max(day_by_number)
    for sunday_day in range(7, max_day + 1, 7):
        previous = day_by_number.get(sunday_day - 1)
        current = day_by_number.get(sunday_day + 1)
        if previous is not None and current is not None:
            boundary_pair = (previous, current)
            break
    if boundary_pair is None:
        for previous, current in zip(book.days, book.days[1:]):
            if _editorial_week_number(previous.day_number) != _editorial_week_number(current.day_number):
                boundary_pair = (previous, current)
                break
    if boundary_pair is None:
        return []
    previous, current = boundary_pair
    previous_anchors = set(_anchor_tokens(previous, topic))
    current_anchors = set(_anchor_tokens(current, topic))
    shared = previous_anchors & current_anchors
    new_terms = current_anchors - previous_anchors
    combined_similarity = _similarity(_combined_day_text(previous), _combined_day_text(current))
    if shared and new_terms and combined_similarity < 0.82:
        return []
    return [
        BookValidatorAssessment(
            check_id="BOOK_WEEK_TRANSITION",
            result="fail",
            reason_code="WEEK_TRANSITION_WEAK",
            explanation=(
                "The week boundary does not show a healthy blend of continuity and fresh movement. "
                "Week two should connect to week one without feeling like a reset or duplicate."
            ),
            evidence=(
                f"boundary={previous.day_number}->{current.day_number} "
                f"shared={sorted(shared)} new_terms={sorted(new_terms)} "
                f"similarity={combined_similarity:.2f}"
            ),
            day_numbers=[previous.day_number, current.day_number],
        )
    ]


def _theological_boundary(day: DailyDevotional, topic: str) -> list[BookValidatorAssessment]:
    scripture_tokens = set(_tokens(day.scripture.text))
    section_tokens = set(_tokens(_combined_day_text(day)))
    passage_themes = [token for token in scripture_tokens if token in _THEOLOGICAL_KEYWORDS]
    if not passage_themes:
        passage_themes = _anchor_tokens(day, topic)
    matched_themes = set(passage_themes) & section_tokens
    findings: list[BookValidatorAssessment] = []
    if not matched_themes and day.scripture.reference.lower() not in _combined_day_text(day).lower():
        findings.append(
            BookValidatorAssessment(
                check_id="BOOK_THEOLOGICAL_BOUNDARY",
                result="fail",
                reason_code="THEOLOGICAL_BOUNDARY_DRIFT",
                explanation=(
                    "The exposition, prayer, and application drift away from the theological burden "
                    "of the day's passage."
                ),
                evidence=f"passage_themes={sorted(set(passage_themes))}",
                day_numbers=[day.day_number],
            )
        )

    severe_in_passage = set(passage_themes) & _SEVERE_THEMES
    severe_in_sections = severe_in_passage & section_tokens
    comfort_in_sections = _COMFORT_THEMES & section_tokens
    if severe_in_passage and not severe_in_sections and comfort_in_sections:
        findings.append(
            BookValidatorAssessment(
                check_id="BOOK_THEOLOGICAL_BOUNDARY",
                result="fail",
                reason_code="THEOLOGICAL_BOUNDARY_FLATTENING",
                explanation=(
                    "The day's application softens a severe passage into generic comfort language. "
                    "Judgment, sin, repentance, suffering, or the cross should not be flattened away."
                ),
                evidence=(
                    f"passage_themes={sorted(severe_in_passage)} "
                    f"comfort_terms={sorted(comfort_in_sections)}"
                ),
                day_numbers=[day.day_number],
            )
        )
    return findings


def validate_devotional_book(book: DevotionalBook) -> list[BookValidatorAssessment]:
    """Return deterministic whole-book quality findings."""
    findings: list[BookValidatorAssessment] = []
    topic = book.input.topic
    for day in book.days:
        findings.extend(_day_coherence(day, topic))
        findings.extend(_theological_boundary(day, topic))
    findings.extend(_day_progression(book))
    findings.extend(_week_transition(book, topic))
    return findings
