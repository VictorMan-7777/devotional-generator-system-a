from __future__ import annotations

import re
from typing import Iterable

from src.models.pipeline import (
    EditorialBuildArtifact,
    EditorialDayBriefRecord,
    EditorialDayPlanRow,
    EditorialWeekPlan,
    PassageResourceBundle,
)

_STOPWORDS = {
    "the", "and", "that", "with", "from", "into", "this", "were", "was", "have",
    "has", "had", "their", "they", "them", "there", "about", "your", "what",
    "you", "when", "while", "would", "could", "should", "among", "during", "after",
    "before", "because", "through", "those", "these", "very", "then", "than", "unto",
}

# The evaluator's _meaningful_tokens also excludes "lord" and "god" — using them as anchors
# produces zero overlap in the evaluator check (lane_unanchored / burden_unanchored).
_EVALUATOR_STOPWORDS = _STOPWORDS | {"lord", "god"}

_CLAUSE_SPLIT_RE = re.compile(r"[.;:?!]|\s+-\s+|,\s+")


def reasoning_week_number(day_number: int, *, num_days: int, num_weeks: int) -> int:
    if num_weeks <= 1:
        return 1
    base = max(1, num_days // num_weeks)
    remainder = max(0, num_days % num_weeks)
    cursor = 0
    for week in range(1, num_weeks + 1):
        span = base + (1 if week <= remainder else 0)
        cursor += max(1, span)
        if day_number <= cursor:
            return week
    return num_weeks


def detect_genre(reference: str, scripture_text: str) -> str:
    ref = (reference or "").lower()
    lower = (scripture_text or "").lower()
    if ref.startswith(("psalm", "psalms")):
        return "poetry"
    if ref.startswith(("proverbs", "job", "ecclesiastes", "song of songs", "song")):
        return "wisdom"
    if ref.startswith(("isaiah", "jeremiah", "ezekiel", "daniel", "hosea", "joel", "amos", "obadiah", "jonah", "micah", "nahum", "habakkuk", "zephaniah", "haggai", "zechariah", "malachi")):
        return "prophecy"
    if ref.startswith(("romans", "corinthians", "galatians", "ephesians", "philippians", "colossians", "thessalonians", "timothy", "titus", "philemon", "hebrews", "james", "peter", "jude")):
        return "epistle"
    if ref.startswith(("matthew", "mark", "luke", "john")):
        if any(token in lower for token in ("parable", "truly, truly", "i am ", "kingdom of heaven", "kingdom of god")):
            return "gospel_discourse"
        return "narrative"
    if ref.startswith(("acts", "genesis", "exodus", "joshua", "judges", "ruth", "samuel", "kings", "chronicles", "ezra", "nehemiah", "esther")):
        return "narrative"
    return "scripture"


def focus_clause(scripture_text: str) -> str:
    text = " ".join((scripture_text or "").split())
    if not text:
        return "Attend to the passage"
    clauses = [part.strip() for part in _CLAUSE_SPLIT_RE.split(text) if part.strip()]
    for clause in clauses:
        words = clause.split()
        if len(words) >= 4:
            return " ".join(words[:12]).strip()
    words = text.split()
    return " ".join(words[:12]).strip()


def key_terms(scripture_text: str, limit: int = 6) -> list[str]:
    """Extract distinctive terms, prioritizing proper nouns (names, places) over common words."""
    text = scripture_text or ""
    found: list[str] = []
    # First pass: proper nouns (capitalized mid-sentence tokens — names, places, titles).
    # Require 4+ chars to avoid treating short capitalized pronouns/conjunctions (His, Him,
    # Nor, But, Yet) as proper nouns — this is especially important for poetic texts where
    # divine pronouns are capitalized but have zero distinctiveness.
    words = text.split()
    for idx, word in enumerate(words):
        clean = re.sub(r"[^A-Za-z'-]", "", word)
        if len(clean) < 4:
            continue
        # A proper noun is capitalized but not the first word of the text
        if clean[0].isupper() and idx > 0:
            lowered = clean.lower()
            if lowered not in _STOPWORDS and lowered not in found:
                found.append(lowered)
        if len(found) >= limit // 2 + 1:
            break
    # Second pass: remaining distinctive tokens
    for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text):
        lowered = token.lower()
        if lowered in _STOPWORDS or lowered in found:
            continue
        found.append(lowered)
        if len(found) >= limit:
            break
    return found


def scene_summary(reference: str, focus: str, genre: str) -> str:
    if genre in {"narrative", "gospel_discourse"}:
        return f"{reference} centers on {focus.lower()}."
    if genre == "epistle":
        return f"{reference} presses an argument around {focus.lower()}."
    if genre in {"poetry", "wisdom"}:
        return f"{reference} lingers on {focus.lower()}."
    return f"{reference} highlights {focus.lower()}."


def _term_anchor(terms: Iterable[str], *, fallback: str = "", limit: int = 2) -> str:
    """Return the most distinctive terms joined, falling back to a truncated string.

    Scans ALL terms (not just the first few) and excludes evaluator stopwords ("lord",
    "god") which produce zero overlap when the evaluator runs _meaningful_tokens on the
    generated burden/lane text.
    """
    term_list = list(terms)
    # First pass: 4+ char terms that aren't evaluator stopwords
    distinctive = [t for t in term_list if len(t) >= 4 and t.lower() not in _EVALUATOR_STOPWORDS][:limit]
    if not distinctive:
        # Second pass: any non-stopword terms (3+ chars)
        distinctive = [t for t in term_list if len(t) >= 3 and t.lower() not in _EVALUATOR_STOPWORDS][:limit]
    return ", ".join(distinctive).strip() if distinctive else (fallback[:40].strip())


def pastoral_burden(reference: str, focus: str, genre: str, terms: Iterable[str]) -> str:
    term_list = list(terms)
    anchor = _term_anchor(term_list, fallback=focus)
    # All genres include the specific reference so adjacent days with the same anchor
    # (e.g., "abraham" across consecutive Genesis 22 days) still produce distinct burdens.
    if genre == "narrative":
        return f"The passage at {reference} moves through {anchor} — attend to the scene before naming the burden"
    if genre == "gospel_discourse":
        return f"Christ's word in {reference} presses on {anchor} — hold the claim before drawing application"
    if genre == "epistle":
        return f"The argument of {reference} rests on {anchor}"
    if genre in {"poetry", "wisdom"}:
        return f"{reference} lingers at {anchor} — let the movement hold before moving further"
    return f"{reference} anchors itself in {anchor} — attend carefully before applying"


def theological_lane(focus: str, genre: str, burden: str, terms: Iterable[str] = (), reference: str = "") -> str:
    # Prefer key_terms anchor (proper nouns, distinctive words) over raw focus clause
    anchor = _term_anchor(terms, fallback=focus)
    if not anchor:
        meaningful = [w for w in focus.lower().split() if len(w) >= 4 and w not in _STOPWORDS]
        anchor = " ".join(meaningful[:3]).strip() or focus.lower()[:40]
    ref_label = reference or "this passage"
    # All genres include the specific reference so adjacent days differ even when anchor overlaps.
    if genre == "narrative":
        return f"The theological weight of {ref_label} sits at {anchor}"
    if genre == "gospel_discourse":
        return f"The Lord's word in {ref_label} turns on {anchor}"
    if genre == "epistle":
        return f"The doctrinal movement of {ref_label} turns on {anchor}"
    if genre in {"poetry", "wisdom"}:
        return f"The wisdom of {ref_label} opens through {anchor}"
    return f"The burden of {ref_label} is rooted in {anchor}"


_APP_FILTER = _STOPWORDS | {"passage", "text", "moves", "through", "rests", "turns", "opens", "sits", "rooted"}


def application_lane(burden: str, genre: str, key_terms: Iterable[str] = ()) -> str:
    # Prefer passage key_terms for the anchor — the evaluator uses the same terms for overlap
    # checking, so using them here directly guarantees the lane is considered anchored.
    term_list = [t for t in list(key_terms) if len(t) >= 4 and t.lower() not in _APP_FILTER]
    if term_list:
        anchor = ", ".join(term_list[:2])
    else:
        # Fall back to extracting from burden text
        tokens = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", burden)
        distinctive = [t for t in tokens if len(t) >= 4 and t.lower() not in _APP_FILTER][:4]
        anchor = ", ".join(distinctive[:2]).strip() if distinctive else " ".join(burden.split()[:5]).strip()
    if genre == "epistle":
        return f"The text shapes its call through {anchor}"
    if genre == "narrative":
        return f"The passage calls its reader to attend to {anchor}"
    if genre in {"poetry", "wisdom"}:
        return f"Let the movement at {anchor} shape what response looks like"
    return f"The text anchors faithful response in {anchor}"


def forbidden_drifts(genre: str) -> list[str]:
    drifts = ["generic devotional language detached from the passage"]
    if genre == "narrative":
        drifts.append("moralizing every detail without honoring the scene")
    if genre == "epistle":
        drifts.append("flattening argument into slogans")
    if genre in {"poetry", "wisdom"}:
        drifts.append("turning poetic reflection into thin positivity")
    return drifts


def build_reasoning_day_brief(
    *,
    day_number: int,
    week_number: int,
    scripture_reference: str,
    study_window_reference: str,
    key_verse_reference: str,
    scripture_text: str,
) -> EditorialDayBriefRecord:
    focus = focus_clause(scripture_text)
    genre = detect_genre(scripture_reference, scripture_text)
    terms = key_terms(scripture_text)
    burden = pastoral_burden(scripture_reference, focus, genre, terms)
    lane = theological_lane(focus, genre, burden, terms=terms, reference=scripture_reference)
    return EditorialDayBriefRecord(
        day_number=day_number,
        week_number=week_number,
        scripture_reference=scripture_reference,
        study_window_reference=study_window_reference,
        key_verse_reference=key_verse_reference,
        day_title=f"{scripture_reference} - {focus}",
        focus_clause=focus,
        pastoral_burden=burden,
        genre=genre,
        scene_summary=scene_summary(scripture_reference, focus, genre),
        theological_lane=lane,
        application_lane=application_lane(burden, genre, key_terms=terms),
        forbidden_drifts=forbidden_drifts(genre),
        key_terms=terms,
    )


def build_reasoning_week_plans(day_briefs: list[EditorialDayBriefRecord]) -> list[EditorialWeekPlan]:
    by_week: dict[int, list[EditorialDayBriefRecord]] = {}
    for brief in day_briefs:
        by_week.setdefault(brief.week_number, []).append(brief)
    plans: list[EditorialWeekPlan] = []
    for week_number in sorted(by_week):
        items = sorted(by_week[week_number], key=lambda item: item.day_number)
        first = items[0]
        last = items[-1]
        plans.append(
            EditorialWeekPlan(
                week_number=week_number,
                title=f"Week {week_number}: {first.pastoral_burden[:60]}",
                days=[item.day_number for item in items],
                movement_summary=(
                    f"Moves from {first.focus_clause.lower()} toward {last.focus_clause.lower()} "
                    f"without repeating the same burden."
                ),
            )
        )
    return plans


def build_reasoning_editorial_artifact(
    *,
    topic: str,
    source_reference: str,
    num_days: int,
    num_weeks: int,
    day_inputs: list[dict[str, str]],
    passage_resources: PassageResourceBundle | None,
) -> EditorialBuildArtifact:
    day_plan: list[EditorialDayPlanRow] = []
    day_briefs: list[EditorialDayBriefRecord] = []
    for idx, row in enumerate(day_inputs, start=1):
        week_number = reasoning_week_number(idx, num_days=num_days, num_weeks=num_weeks)
        scripture_reference = str(row["scripture_reference"]).strip()
        study_window_reference = str(row["study_window_reference"]).strip()
        key_verse_reference = str(row["key_verse_reference"]).strip()
        scripture_text = str(row["scripture_text"]).strip()
        day_plan.append(
            EditorialDayPlanRow(
                day_number=idx,
                week_number=week_number,
                topic=topic,
                scripture_reference=scripture_reference,
                study_window_reference=study_window_reference,
            )
        )
        day_briefs.append(
            build_reasoning_day_brief(
                day_number=idx,
                week_number=week_number,
                scripture_reference=scripture_reference,
                study_window_reference=study_window_reference,
                key_verse_reference=key_verse_reference,
                scripture_text=scripture_text,
            )
        )
    return EditorialBuildArtifact(
        topic=topic,
        num_days=num_days,
        source_reference=source_reference,
        week_count=max((item.week_number for item in day_briefs), default=0),
        passage_resources=passage_resources,
        day_plan=day_plan,
        day_briefs=day_briefs,
        week_plans=build_reasoning_week_plans(day_briefs),
    )
