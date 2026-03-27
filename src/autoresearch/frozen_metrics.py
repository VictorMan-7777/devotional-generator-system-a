"""frozen_metrics.py — Deterministic scoring functions for Be Still, Action Steps, Exposition.

No LLM. No API. No randomness. Same input → same score, always.
Source: docs/system/frozen-metrics-spec.md (Grok 4.20 + Claude review, 2026-03-19)
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STOP_WORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any",
    "are", "aren't", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "can't", "cannot", "could", "couldn't", "did", "didn't",
    "do", "does", "doesn't", "doing", "don't", "down", "during", "each", "few", "for",
    "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he",
    "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself", "him", "himself",
    "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is",
    "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd",
    "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than", "that", "that's",
    "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these",
    "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're",
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's",
    "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself",
    "yourselves",
    # KJV / archaic biblical English
    "thee", "thou", "thy", "thine", "hath", "doth", "hast", "ye", "art", "unto", "upon",
    "thereof", "whereof", "whence", "whither",
})

REFORMED_CONCEPTS = frozenset({
    "grace", "justification", "sanctification", "covenant", "election", "atonement",
    "sovereignty", "providence", "imputation", "adoption", "perseverance",
    "union with christ", "regeneration", "repentance", "propitiation", "reconciliation",
    "redemption", "intercession", "glorification", "total depravity", "calling",
    "resurrection",
})

BE_STILL_TEMPLATE_PATTERNS = [
    r"concrete obedience that takes .{1,40} seriously rather than at a distance",
    r"scene of .{1,60} slowly and let it settle",
    r"faithful response to god.?s word",
    r"truthfulness under pressure",
    r"new allegiance demanded by",
    r"sit with .{1,40} for two quiet minutes",
]

ACTION_STEPS_META_PATTERNS = [
    r"write one sentence naming how",
    r"name one place where",
    r"pause and ask how .{1,60} should shape",
    r"how .{1,60} presses on",
]

ACTION_STEPS_BOILERPLATE_PATTERNS = [
    r"concrete obedience",
    r"costly act of obedience",
    r"cross-shaped faithfulness",
    r"grateful obedience within god.?s generous boundaries",
]

EXPOSITION_BOILERPLATE_PATTERNS = [
    r"opens with a scene marked by",
    r"worship and wisdom under the word of god",
    r"must be received before it is applied",
    r"the passage puts one clear scene in front of us",
]

SAME_DAY_TANGIBLE_PATTERN = re.compile(
    r"today|now|this morning|this evening|tell one person|write down|"
    r"physically|call|send a message|before you",
    re.IGNORECASE,
)

EMOTIONAL_BODILY_PATTERN = re.compile(
    r"feel|heart|body|resist|rest|fear|trust|grieve|rejoice|ache|still|weight",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Signature extraction
# ---------------------------------------------------------------------------

def extract_signature(scripture_text: str) -> tuple[set[str], set[str], set[str]]:
    """Return (keywords, passage_phrases, strict_bigrams) from a scripture text.

    - keywords: individual content words
    - passage_phrases: relaxed bigrams (≥1 content word) + relaxed trigrams (≥2 content words)
    - strict_bigrams: both words are content words (used only for bonus tier)
    """
    text = re.sub(r"[^a-zA-Z\s]", " ", scripture_text.lower())
    words = text.split()

    keywords: set[str] = {w for w in words if w not in STOP_WORDS and len(w) > 1}

    relaxed_bigrams: set[str] = {
        f"{words[i]} {words[i+1]}"
        for i in range(len(words) - 1)
        if (words[i] not in STOP_WORDS) or (words[i+1] not in STOP_WORDS)
    }

    strict_bigrams: set[str] = {
        f"{words[i]} {words[i+1]}"
        for i in range(len(words) - 1)
        if words[i] not in STOP_WORDS and words[i+1] not in STOP_WORDS
    }

    relaxed_trigrams: set[str] = {
        f"{words[i]} {words[i+1]} {words[i+2]}"
        for i in range(len(words) - 2)
        if sum(w not in STOP_WORDS for w in words[i:i+3]) >= 2
    }

    passage_phrases = relaxed_bigrams | relaxed_trigrams
    return keywords, passage_phrases, strict_bigrams


def _text_keywords(text: str) -> set[str]:
    clean = re.sub(r"[^a-zA-Z\s]", " ", text.lower())
    return {w for w in clean.split() if w not in STOP_WORDS and len(w) > 1}


# ---------------------------------------------------------------------------
# Proximity helper
# ---------------------------------------------------------------------------

def is_within_window(text: str, target_phrase: str, window_size: int = 15) -> bool:
    """Return True if '?' appears within ±window_size tokens of target_phrase."""
    tokens = text.lower().split()
    phrase_tokens = target_phrase.lower().split()
    phrase_len = len(phrase_tokens)
    for i in range(len(tokens) - phrase_len + 1):
        if tokens[i:i + phrase_len] == phrase_tokens:
            left = max(0, i - window_size)
            right = min(len(tokens), i + phrase_len + window_size)
            window_text = "".join(tokens[left:right])
            if "?" in window_text:
                return True
    return False


def _has_phrase_near_question(prompt: str, phrases: set[str], window: int = 15) -> bool:
    """Return True if any phrase from the set appears near a '?' in the same prompt."""
    for phrase in phrases:
        if phrase in prompt.lower() and is_within_window(prompt, phrase, window):
            return True
    return False


# ---------------------------------------------------------------------------
# Be Still scorer
# ---------------------------------------------------------------------------

def score_be_still(prompts: list[str], scripture_text: str) -> dict[str, Any]:
    """Score a Be Still section (0–100).

    Pass >= 80, Revise >= 60, Fail < 60.
    Expected range for current template output: 35–42.
    """
    passage_keywords, passage_phrases, strict_bigrams = extract_signature(scripture_text)
    section_text = " ".join(prompts)
    section_keywords = _text_keywords(section_text)

    components: dict[str, int] = {}
    penalties: list[str] = []
    bonuses: list[str] = []

    # --- Required base (0–60) ---

    # Proportional intersection floor
    required_min = max(3, len(passage_keywords) // 3)
    keyword_overlap = len(section_keywords & passage_keywords)
    if keyword_overlap >= required_min:
        components["keyword_intersection"] = 25
    elif keyword_overlap >= required_min - 1:
        components["keyword_intersection"] = 15
    elif keyword_overlap >= required_min - 2:
        components["keyword_intersection"] = 5
    else:
        components["keyword_intersection"] = 0

    # At least one relaxed phrase anywhere in section
    section_lower = section_text.lower()
    phrase_in_section = any(p in section_lower for p in passage_phrases)
    components["phrase_in_section"] = 15 if phrase_in_section else 0
    if phrase_in_section:
        bonuses.append("relaxed_phrase_present")

    # At least one individual prompt has both '?' and a relaxed phrase (same prompt)
    prompt_with_question_and_phrase = any(
        "?" in p and any(phrase in p.lower() for phrase in passage_phrases)
        for p in prompts
    )
    components["question_with_phrase"] = 20 if prompt_with_question_and_phrase else 0
    if prompt_with_question_and_phrase:
        bonuses.append("question_with_passage_phrase")

    # --- Template penalties ---
    penalty_total = 0
    for pattern in BE_STILL_TEMPLATE_PATTERNS:
        if re.search(pattern, section_lower):
            penalty_total += 15
            penalties.append(pattern)
    penalty_total = min(penalty_total, 60)
    components["template_penalty"] = -penalty_total

    # --- Bonus points (0–40) ---

    # Strict bigram in a question (higher-quality bonus)
    strict_in_question = any(
        _has_phrase_near_question(p, strict_bigrams) for p in prompts
    )
    components["strict_bigram_in_question"] = 15 if strict_in_question else 0
    if strict_in_question:
        bonuses.append("strict_bigram_in_question")

    # Average prompt length > 22 words
    avg_len = sum(len(p.split()) for p in prompts) / max(len(prompts), 1)
    components["avg_prompt_length"] = 10 if avg_len > 22 else 0
    if avg_len > 22:
        bonuses.append("avg_prompt_length_>22")

    # Emotional/bodily keyword near a passage keyword
    emotional_near_keyword = False
    for p in prompts:
        p_lower = p.lower()
        p_words = p_lower.split()
        for i, word in enumerate(p_words):
            if word in passage_keywords:
                window_slice = " ".join(p_words[max(0, i-15):i+16])
                if EMOTIONAL_BODILY_PATTERN.search(window_slice):
                    emotional_near_keyword = True
                    break
        if emotional_near_keyword:
            break
    components["emotional_keyword_near_passage"] = 15 if emotional_near_keyword else 0
    if emotional_near_keyword:
        bonuses.append("emotional_keyword_near_passage")

    score = sum(v for v in components.values())
    score = max(0, min(100, score))

    if score >= 80:
        status = "pass"
    elif score >= 60:
        status = "revise"
    else:
        status = "fail"

    return {
        "score": score,
        "status": status,
        "components": components,
        "penalties_applied": penalties,
        "bonuses_applied": bonuses,
        "keyword_overlap": keyword_overlap,
        "required_min": required_min,
        "passage_keyword_count": len(passage_keywords),
    }


# ---------------------------------------------------------------------------
# Action Steps scorer
# ---------------------------------------------------------------------------

def score_action_steps(
    connector: str, items: list[str], scripture_text: str
) -> dict[str, Any]:
    """Score an Action Steps section (0–100).

    Pass >= 80, Revise >= 60, Fail < 60.
    Expected range for current template output: 15–22.
    """
    passage_keywords, passage_phrases, _ = extract_signature(scripture_text)
    connector_lower = connector.lower()
    all_steps_text = " ".join(items).lower()

    components: dict[str, int] = {}
    penalties: list[str] = []
    bonuses: list[str] = []

    # --- Required base (0–60) ---

    # Clean connector
    connector_template_hit = bool(re.search(
        r"because .{1,60} calls for concrete obedience that takes .{1,40} "
        r"seriously rather than at a distance today",
        connector_lower,
    ))
    components["clean_connector"] = 0 if connector_template_hit else 25
    if connector_template_hit:
        penalties.append("connector_template_match")

    # ≥2 steps with passage keyword or phrase
    steps_with_passage = sum(
        1 for item in items
        if any(kw in item.lower() for kw in passage_keywords)
        or any(ph in item.lower() for ph in passage_phrases)
    )
    if steps_with_passage >= 2:
        components["steps_with_passage_content"] = 20
        bonuses.append("steps_with_passage_content")
    else:
        components["steps_with_passage_content"] = 0

    # Zero meta-reading instructions
    meta_hit = any(
        re.search(p, all_steps_text) for p in ACTION_STEPS_META_PATTERNS
    )
    components["no_meta_steps"] = 0 if meta_hit else 15
    if meta_hit:
        penalties.append("meta_reading_instruction")

    # --- Additional penalties ---
    boilerplate_penalty = 0
    for pattern in ACTION_STEPS_BOILERPLATE_PATTERNS:
        full_text = connector_lower + " " + all_steps_text
        if re.search(pattern, full_text):
            boilerplate_penalty += 15
            penalties.append(pattern)
    boilerplate_penalty = min(boilerplate_penalty, 45)
    components["boilerplate_penalty"] = -boilerplate_penalty

    # Meta penalty (applied separately, not capped with boilerplate)
    if meta_hit:
        components["meta_step_penalty"] = -30
    else:
        components["meta_step_penalty"] = 0

    # --- Bonus points (0–40) ---

    # Same-day tangible marker in at least one step
    tangible = any(SAME_DAY_TANGIBLE_PATTERN.search(item) for item in items)
    components["same_day_tangible"] = 20 if tangible else 0
    if tangible:
        bonuses.append("same_day_tangible_marker")

    # Grace-response framing
    grace_response = False
    for item in items:
        item_lower = item.lower()
        item_words = item_lower.split()
        has_because = bool(re.search(r"\bbecause\b|\bsince\b|\btherefore\b", item_lower))
        has_grace = bool(re.search(
            r"god has|christ has|the lord|mercy|grace", item_lower
        ))
        has_passage_kw = any(kw in item_lower for kw in passage_keywords)
        if has_because and has_grace and has_passage_kw:
            grace_response = True
            break
    components["grace_response_framing"] = 15 if grace_response else 0
    if grace_response:
        bonuses.append("grace_response_framing")

    # Connector contains a passage phrase
    connector_has_phrase = any(ph in connector_lower for ph in passage_phrases)
    components["connector_has_passage_phrase"] = 5 if connector_has_phrase else 0
    if connector_has_phrase:
        bonuses.append("connector_has_passage_phrase")

    score = sum(v for v in components.values())
    score = max(0, min(100, score))

    if score >= 80:
        status = "pass"
    elif score >= 60:
        status = "revise"
    else:
        status = "fail"

    return {
        "score": score,
        "status": status,
        "components": components,
        "penalties_applied": penalties,
        "bonuses_applied": bonuses,
    }


# ---------------------------------------------------------------------------
# Exposition scorer
# ---------------------------------------------------------------------------

def score_exposition(text: str, scripture_text: str) -> dict[str, Any]:
    """Score an Exposition section (0–100)."""
    passage_keywords, _, _ = extract_signature(scripture_text)
    text_lower = text.lower()

    components: dict[str, int] = {}
    penalties: list[str] = []
    bonuses: list[str] = []

    # Word count 280–550
    word_count = len(text.split())
    components["word_count"] = 20 if 280 <= word_count <= 550 else 0
    if 280 <= word_count <= 550:
        bonuses.append("word_count_in_range")

    # Direct quote or 5+ word sequence from passage
    scripture_clean = re.sub(r"[^a-zA-Z\s]", " ", scripture_text.lower())
    scripture_words = scripture_clean.split()
    found_quote = False
    for i in range(len(scripture_words) - 4):
        seq = " ".join(scripture_words[i:i+5])
        if seq in text_lower:
            found_quote = True
            break
    components["passage_quote"] = 20 if found_quote else 0
    if found_quote:
        bonuses.append("passage_quote_present")

    # Reformed theological concept
    has_concept = any(c in text_lower for c in REFORMED_CONCEPTS)
    components["reformed_concept"] = 20 if has_concept else 0
    if has_concept:
        bonuses.append("reformed_concept_present")

    # No forbidden boilerplate
    boilerplate_hits = [p for p in EXPOSITION_BOILERPLATE_PATTERNS if re.search(p, text_lower)]
    components["no_boilerplate"] = 0 if boilerplate_hits else 10
    penalties.extend(boilerplate_hits)

    # No sentence fragments (rough check: sentences 8–70 words)
    sentences = re.split(r"[.!?]", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    fragment_count = sum(
        1 for s in sentences if len(s.split()) < 8 or len(s.split()) > 70
    )
    components["no_fragments"] = 10 if fragment_count == 0 else 0

    # ≥3 unique passage keywords each appear ≥1 time
    kw_present = {kw for kw in passage_keywords if kw in text_lower}
    components["passage_keywords"] = 20 if len(kw_present) >= 3 else 0

    # Obsessive repetition penalty — any 2-3 word phrase >4 times
    words_list = text_lower.split()
    phrases_2 = [" ".join(words_list[i:i+2]) for i in range(len(words_list)-1)]
    phrases_3 = [" ".join(words_list[i:i+3]) for i in range(len(words_list)-2)]
    repetition_penalty = 0
    for phrase_list in [phrases_2, phrases_3]:
        from collections import Counter
        counts = Counter(phrase_list)
        for phrase, count in counts.items():
            # skip trivial stop-word-only phrases
            phrase_words = phrase.split()
            if all(w in STOP_WORDS for w in phrase_words):
                continue
            if count > 4:
                repetition_penalty = -10
                penalties.append(f"repetition: '{phrase}' x{count}")
                break
        if repetition_penalty:
            break
    components["repetition_penalty"] = repetition_penalty

    score = sum(v for v in components.values())
    score = max(0, min(100, score))

    if score >= 80:
        status = "pass"
    elif score >= 60:
        status = "revise"
    else:
        status = "fail"

    return {
        "score": score,
        "status": status,
        "components": components,
        "penalties_applied": penalties,
        "bonuses_applied": bonuses,
        "word_count": word_count,
        "passage_keywords_present": sorted(kw_present),
    }


# ---------------------------------------------------------------------------
# Prayer frozen metric
# ---------------------------------------------------------------------------

# Words that signal lament/anguish tone — expected in lament-theme prayers
_LAMENT_TONE_WORDS = frozenset({
    "lament", "grief", "sorrow", "forsaken", "cry", "anguish", "cast down",
    "desolate", "weeping", "mourning", "afflicted", "troubled", "distressed",
})

# Words that signal comfort/trust/joy tone — expected in trust/praise prayers
_COMFORT_TONE_WORDS = frozenset({
    "comfort", "peace", "joy", "rest", "hope", "blessing", "rejoice",
    "gladness", "delight", "trust", "shelter", "refuge", "strength",
})

# Themes where the prayer tone should skew toward lament (comfort words alone = mismatch)
_LAMENT_THEMES = frozenset({"psalm_lament", "loss", "affliction", "endurance"})

# Themes where lament words alone (with no comfort) = mismatch
_COMFORT_THEMES = frozenset({"psalm_trust", "psalm_praise", "resurrection", "prophecy_restoration"})

# Theological terms that, if present in the prayer but absent from the passage signature,
# suggest imported concepts rather than passage-grounded content
_IMPORTED_THEOLOGY_WORDS = frozenset({
    "atonement", "election", "imputation", "predestination", "depravity",
    "propitiation", "glorification", "perseverance",
})


def score_prayer(
    prayer_text: str,
    brief_focus_clause: str,
    brief_pastoral_burden: str,
    brief_application_lane: str,
    scripture_text: str,
    theme_key: str,
    scripture_reference: str,
) -> dict[str, Any]:
    """Deterministic frozen metric for the Prayer worker.

    No LLM. Same input → same score always.
    Returns {score, status, components, penalties_applied, bonuses_applied}.
    Pass ≥ 80, Revise ≥ 60, Fail < 60.
    """
    keywords, passage_phrases, _ = extract_signature(scripture_text)
    prayer_lower = prayer_text.strip().lower()

    penalties: list[tuple[str, int]] = []
    bonuses: list[tuple[str, int]] = []
    components: dict[str, Any] = {}
    score = 100

    # ------------------------------------------------------------------
    # Structural guarantees (checked; not penalized since always present
    # in a correctly-built prayer — but absence is a hard failure signal)
    # ------------------------------------------------------------------
    has_amen = prayer_text.strip().endswith("Amen.")
    burden_in_prayer = brief_pastoral_burden.lower()[:40] in prayer_lower
    components["structural"] = {"has_amen": has_amen, "burden_embedded": burden_in_prayer}
    if not has_amen:
        penalties.append(("missing Amen.", -20))
    if not burden_in_prayer:
        penalties.append(("pastoral burden not embedded in prayer", -15))

    # ------------------------------------------------------------------
    # 1. Passage keyword / phrase density (0–25 pts; deduct shortfall)
    # ------------------------------------------------------------------
    prayer_words = _text_keywords(prayer_lower)
    keyword_overlap = len(prayer_words & keywords)
    phrase_hits = sum(1 for p in passage_phrases if p in prayer_lower and len(p) > 6)
    overlap_score = min(25, keyword_overlap * 3 + phrase_hits * 2)
    shortfall = 25 - overlap_score
    if shortfall > 0:
        penalties.append((f"low passage keyword overlap (overlap={keyword_overlap}, phrases={phrase_hits})", -shortfall))
    components["passage_overlap"] = {"keyword_overlap": keyword_overlap, "phrase_hits": phrase_hits, "score": overlap_score}

    # ------------------------------------------------------------------
    # 2. Focus clause present in petition body (beyond the fixed opener)
    # ------------------------------------------------------------------
    sentences = re.split(r"(?<=[.!?])\s+", prayer_text)
    petition_body = " ".join(sentences[3:]).lower() if len(sentences) > 3 else ""
    focus_tokens = [t for t in _text_keywords(brief_focus_clause) if len(t) > 3]
    focus_in_petition = bool(focus_tokens) and any(t in petition_body for t in focus_tokens)
    components["focus_in_petition"] = focus_in_petition
    if focus_in_petition:
        bonuses.append(("focus clause echoed in petition body", 12))
    else:
        penalties.append(("focus clause absent from petition body", -12))

    # ------------------------------------------------------------------
    # 3. Tone match (lament themes should not be all comfort; vice versa)
    # ------------------------------------------------------------------
    has_lament_tone = any(w in prayer_lower for w in _LAMENT_TONE_WORDS)
    has_comfort_tone = any(w in prayer_lower for w in _COMFORT_TONE_WORDS)
    tone_ok = True
    if theme_key in _LAMENT_THEMES:
        # Lament theme: if only comfort words present and no lament words → mismatch
        if has_comfort_tone and not has_lament_tone:
            tone_ok = False
            penalties.append(("comfort-only tone for lament theme", -18))
    elif theme_key in _COMFORT_THEMES:
        # Trust/praise/restoration: if only lament words and no comfort words → mismatch
        if has_lament_tone and not has_comfort_tone:
            tone_ok = False
            penalties.append(("lament-only tone for trust/praise theme", -12))
    components["tone"] = {"theme_key": theme_key, "has_lament_tone": has_lament_tone, "has_comfort_tone": has_comfort_tone, "tone_ok": tone_ok}

    # ------------------------------------------------------------------
    # 4. Imported theological concepts (words not in passage signature)
    # ------------------------------------------------------------------
    imported = {w for w in _IMPORTED_THEOLOGY_WORDS if w in prayer_lower and w not in keywords}
    if len(imported) >= 2:
        penalties.append((f"imported theological concepts absent from passage: {', '.join(sorted(imported))}", -10))
    components["imported_concepts"] = sorted(imported)

    # ------------------------------------------------------------------
    # Apply and clamp
    # ------------------------------------------------------------------
    for _, pts in bonuses:
        score += pts
    for _, pts in penalties:
        score += pts
    score = max(0, min(100, score))

    status = "pass" if score >= 80 else "revise" if score >= 60 else "fail"
    return {
        "score": score,
        "status": status,
        "components": components,
        "penalties_applied": penalties,
        "bonuses_applied": bonuses,
    }


# ---------------------------------------------------------------------------
# Novelty gate (for proposal ledger)
# ---------------------------------------------------------------------------

def is_novel_proposal(
    proposed_patch: list[dict],
    ledger_path: Path | str,
    similarity_threshold: float = 0.85,
) -> bool:
    """Return True if the proposed patch is sufficiently different from recent attempts."""
    current_hash = hashlib.sha256(
        json.dumps(proposed_patch, sort_keys=True).encode()
    ).hexdigest()
    try:
        lines = Path(ledger_path).read_text().splitlines()[-50:]
    except FileNotFoundError:
        return True
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("proposal_hash") == current_hash:
            return False
        sim = difflib.SequenceMatcher(
            None,
            json.dumps(proposed_patch, sort_keys=True),
            json.dumps(entry.get("patch", []), sort_keys=True),
        ).ratio()
        if sim > similarity_threshold:
            return False
    return True
