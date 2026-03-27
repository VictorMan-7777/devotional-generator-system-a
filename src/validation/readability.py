from __future__ import annotations

import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ReadabilityScore:
    word_count: int
    sentence_count: int
    syllable_count: int
    flesch_reading_ease: float
    flesch_kincaid_grade: float


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")


def _sentence_count(text: str) -> int:
    count = len(re.findall(r"[.!?]+", text or ""))
    return max(1, count)


def _syllables_in_word(word: str) -> int:
    token = re.sub(r"[^a-z]", "", word.lower())
    if not token:
        return 0
    vowels = "aeiouy"
    groups = 0
    prev_vowel = False
    for ch in token:
        is_vowel = ch in vowels
        if is_vowel and not prev_vowel:
            groups += 1
        prev_vowel = is_vowel
    if token.endswith("e") and groups > 1:
        groups -= 1
    if token.endswith("le") and len(token) > 2 and token[-3] not in vowels:
        groups += 1
    return max(1, groups)


def score_text(text: str) -> ReadabilityScore:
    words = _WORD_RE.findall(text or "")
    word_count = max(1, len(words))
    sentence_count = _sentence_count(text)
    syllable_count = sum(_syllables_in_word(word) for word in words) or 1

    words_per_sentence = word_count / sentence_count
    syllables_per_word = syllable_count / word_count
    ease = 206.835 - (1.015 * words_per_sentence) - (84.6 * syllables_per_word)
    grade = (0.39 * words_per_sentence) + (11.8 * syllables_per_word) - 15.59
    return ReadabilityScore(
        word_count=word_count,
        sentence_count=sentence_count,
        syllable_count=syllable_count,
        flesch_reading_ease=round(ease, 2),
        flesch_kincaid_grade=round(grade, 2),
    )


def grade_band_label(score: ReadabilityScore) -> str:
    grade = score.flesch_kincaid_grade
    if grade <= 5:
        return "very_easy"
    if grade <= 8:
        return "target"
    if grade <= 10:
        return "needs_simplification"
    return "hard"


def section_readability_report(text: str) -> dict[str, float | int | str]:
    score = score_text(text)
    return {
        "word_count": score.word_count,
        "sentence_count": score.sentence_count,
        "syllable_count": score.syllable_count,
        "flesch_reading_ease": score.flesch_reading_ease,
        "flesch_kincaid_grade": score.flesch_kincaid_grade,
        "grade_band": grade_band_label(score),
    }
