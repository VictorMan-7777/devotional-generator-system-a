"""modernization.py — FR-56 archaic language modernization.

Applies regex substitutions to text before any retrieved content is used
in generation. Preserves negation/modality phrases by protecting them
before substitution and restoring them after.

Critical: "shall not" must remain "shall not" — never "may not".
"""
from __future__ import annotations

import re

# Modern negation/modal phrases protected before any substitution.
# Archaic forms (shalt not, wilt not, hath not) are NOT protected here —
# they pass through verb substitution (shalt→shall, wilt→will, hath→has),
# which is the desired transformation. Only modern forms are protected to
# guard against hypothetical future rules that might alter modality level.
_PROTECTED_PHRASES: list[str] = [
    "shall not",
    "will not",
    "would not",
    "should not",
    "could not",
    "might not",
    "may not",
    "cannot",
    "can not",
]

# Archaic pronoun substitutions.
_ARCHAIC_PRONOUNS: list[tuple[str, str]] = [
    (r"\bthine\b", "yours"),   # possessive; before "thy" to avoid partial overlap
    (r"\bthy\b", "your"),
    (r"\bthee\b", "you"),
    (r"\bthou\b", "you"),
    (r"\bye\b", "you"),        # plural second-person
]

# Archaic verb substitutions.
_ARCHAIC_VERBS: list[tuple[str, str]] = [
    (r"\bhath\b", "has"),
    (r"\bhast\b", "have"),
    (r"\bdoth\b", "does"),
    (r"\bdost\b", "do"),
    (r"\bcometh\b", "comes"),
    (r"\bsaith\b", "says"),
    (r"\bsaieth\b", "says"),
    (r"\bwilt\b", "will"),
    (r"\bwouldst\b", "would"),
    (r"\bcanst\b", "can"),
    (r"\bcouldst\b", "could"),
    (r"\bshouldst\b", "should"),
    (r"\bshalt\b", "shall"),
    (r"\bseeth\b", "sees"),
    (r"\bknoweth\b", "knows"),
    (r"\bgiveth\b", "gives"),
    (r"\bleadeth\b", "leads"),
]

# Shifted-meaning terms (archaic sense only).
_SHIFTED_MEANING: list[tuple[str, str]] = [
    (r"\bcharity\b", "love"),
    (r"\bconversation\b", "conduct"),
    (r"\bprevent\b", "precede"),
]


def modernize(text: str) -> str:
    """Apply FR-56 archaic language substitutions to retrieved text.

    Protected negation/modal phrases are shielded from substitution
    and restored exactly after all other transforms complete.
    Substitutions are applied case-insensitively; protected phrases
    are restored using their original lowercased canonical forms.
    """
    # Step 1: protect negation/modal phrases with unique placeholders.
    placeholders: dict[str, str] = {}
    for i, phrase in enumerate(_PROTECTED_PHRASES):
        placeholder = f"__PROTECTED_{i}__"
        text, count = re.subn(
            rf"\b{re.escape(phrase)}\b", placeholder, text, flags=re.IGNORECASE
        )
        if count:
            placeholders[placeholder] = phrase

    # Step 2: apply archaic pronoun substitutions.
    for pattern, replacement in _ARCHAIC_PRONOUNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Step 3: apply archaic verb substitutions.
    for pattern, replacement in _ARCHAIC_VERBS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Step 4: apply shifted-meaning substitutions.
    for pattern, replacement in _SHIFTED_MEANING:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Step 5: restore protected phrases.
    for placeholder, phrase in placeholders.items():
        text = text.replace(placeholder, phrase)

    return text
