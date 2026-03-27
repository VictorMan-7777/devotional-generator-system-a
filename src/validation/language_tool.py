from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class LanguageToolIssue:
    rule_id: str
    message: str
    offset: int
    length: int
    replacements: tuple[str, ...]
    category: str


@dataclass(frozen=True)
class LanguageToolAdvisory:
    day_number: int
    section: str
    rule_id: str
    message: str
    category: str
    context: str
    replacements: tuple[str, ...]


def _find_binary() -> str | None:
    return shutil.which("languagetool")


def check_text(text: str, *, language: str = "en-US", ignored_words: set[str] | None = None) -> list[LanguageToolIssue]:
    binary = _find_binary()
    if binary is None or not text.strip():
        return []

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)

    try:
        proc = subprocess.run(
            [binary, "--json", "-l", language, str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return []
        payload = json.loads(proc.stdout)
    finally:
        tmp_path.unlink(missing_ok=True)

    ignored = {word.lower() for word in (ignored_words or set())}
    issues: list[LanguageToolIssue] = []
    for match in payload.get("matches", []):
        token = text[match.get("offset", 0): match.get("offset", 0) + match.get("length", 0)]
        if token.lower() in ignored:
            continue
        issues.append(
            LanguageToolIssue(
                rule_id=str(match.get("rule", {}).get("id", "")),
                message=str(match.get("message", "")),
                offset=int(match.get("offset", 0)),
                length=int(match.get("length", 0)),
                replacements=tuple(
                    str(item.get("value", ""))
                    for item in match.get("replacements", [])
                    if str(item.get("value", "")).strip()
                ),
                category=str(match.get("rule", {}).get("category", {}).get("id", "")),
            )
        )
    return issues


def apply_safe_fixes(text: str, *, language: str = "en-US", ignored_words: set[str] | None = None) -> str:
    issues = check_text(text, language=language, ignored_words=ignored_words)
    if not issues:
        return text

    chars = list(text)
    for issue in sorted(issues, key=lambda item: item.offset, reverse=True):
        replacement = None
        if issue.rule_id == "UPPERCASE_SENTENCE_START" and issue.replacements:
            replacement = issue.replacements[0]
        if not replacement:
            continue
        start = issue.offset
        end = issue.offset + issue.length
        chars[start:end] = list(replacement)
    return "".join(chars)


def _context_snippet(text: str, offset: int, length: int, radius: int = 40) -> str:
    start = max(0, offset - radius)
    end = min(len(text), offset + length + radius)
    return " ".join(text[start:end].split()).strip()


def _capitalized_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"\b[A-Z][A-Za-z'-]+\b", text or "")
        if len(token) > 1
    }


def collect_book_advisories(
    book_payload: dict[str, Any],
    *,
    editorial_build_payload: dict[str, Any] | None = None,
    language: str = "en-US",
    max_per_section: int = 3,
) -> list[LanguageToolAdvisory]:
    days = book_payload.get("days")
    if not isinstance(days, list):
        return []

    day_briefs = (
        editorial_build_payload.get("day_briefs", [])
        if isinstance(editorial_build_payload, dict)
        else []
    )
    advisories: list[LanguageToolAdvisory] = []

    for day in days:
        if not isinstance(day, dict):
            continue
        day_number = int(day.get("day_number", 0) or 0)
        if day_number <= 0:
            continue
        brief = (
            day_briefs[day_number - 1]
            if isinstance(day_briefs, list) and 0 < day_number <= len(day_briefs)
            else {}
        )
        ignored_words = set()
        scripture = day.get("scripture") if isinstance(day.get("scripture"), dict) else {}
        ignored_words.update(_capitalized_tokens(str(scripture.get("reference", ""))))
        ignored_words.update(_capitalized_tokens(str(day.get("day_focus", ""))))
        ignored_words.update(_capitalized_tokens(str(brief.get("focus_clause", ""))))
        ignored_words.update(str(term) for term in brief.get("key_terms", []) if str(term).strip())

        section_texts: list[tuple[str, str]] = []
        exposition = day.get("exposition")
        if isinstance(exposition, dict):
            section_texts.append(("exposition", str(exposition.get("text", ""))))
        prayer = day.get("prayer")
        if isinstance(prayer, dict):
            section_texts.append(("prayer", str(prayer.get("text", ""))))
        be_still = day.get("be_still")
        if isinstance(be_still, dict):
            section_texts.append(("be_still", "\n".join(str(x) for x in be_still.get("prompts", []))))
        action_steps = day.get("action_steps")
        if isinstance(action_steps, dict):
            items = [str(x) for x in action_steps.get("items", [])]
            connector = str(action_steps.get("connector_phrase", "")).strip()
            section_texts.append(("action_steps", "\n".join(([connector] if connector else []) + items)))

        for section, text in section_texts:
            issues = check_text(text, language=language, ignored_words=ignored_words)
            for issue in issues[:max_per_section]:
                advisories.append(
                    LanguageToolAdvisory(
                        day_number=day_number,
                        section=section,
                        rule_id=issue.rule_id,
                        message=issue.message,
                        category=issue.category,
                        context=_context_snippet(text, issue.offset, issue.length),
                        replacements=issue.replacements[:3],
                    )
                )
    return advisories
