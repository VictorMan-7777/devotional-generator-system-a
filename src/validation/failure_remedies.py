from __future__ import annotations

from typing import Any


_REMEDY_MAP: dict[str, list[str]] = {
    "BOOK_DAY_PROGRESS": [
        "Split adjacent days into more distinct passage burdens before rewriting prose.",
        "Rework outline boundaries when adjacent days are drawing from the same movement.",
        "Retrieve more expositional support for the overlapping days instead of padding the exposition.",
    ],
    "BOOK_WEEK_TRANSITION": [
        "Rework the week boundary so week two begins on a real turn in the passage arc.",
        "Adjust the outline so the Sunday/gathered-worship handoff feels earned rather than abrupt.",
        "Strengthen week-level movement in the editorial build before redrafting sections.",
    ],
    "BOOK_THEOLOGICAL_BOUNDARY": [
        "Reassign the theological lane before rewriting prose.",
        "Prefer book-specific commentary structure over whole-Bible commentary if outline help is needed.",
        "Reduce generic devotional language and keep application inside the passage horizon.",
    ],
    "EXPOSITION_WORD_COUNT": [
        "Increase expositional research depth before expanding the exposition.",
        "Sharpen the passage burden so the exposition grows from substance rather than filler.",
        "Trim or expand only after the exposition becomes outstanding, not merely longer.",
    ],
    "EXPOSITION_VOICE": [
        "Remove scripture-fragment leakage and second-person drift before redrafting.",
        "Keep the exposition voice tied to the passage scene instead of copied phrasing.",
    ],
}


def remedy_suggestions(
    failed_check_ids: list[str],
    *,
    attempted_remedies: list[str] | None = None,
) -> dict[str, Any]:
    attempted = [str(item).strip() for item in (attempted_remedies or []) if str(item).strip()]
    by_check: dict[str, list[str]] = {}
    merged: list[str] = []
    for check_id in failed_check_ids:
        suggestions = _REMEDY_MAP.get(str(check_id).strip(), [])
        if suggestions:
            by_check[str(check_id)] = suggestions
        for item in suggestions:
            if item not in merged:
                merged.append(item)
    return {
        "attempted_remedies": attempted,
        "suggested_remedies": merged,
        "suggested_by_check": by_check,
    }
