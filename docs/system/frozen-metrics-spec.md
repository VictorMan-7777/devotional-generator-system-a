# DevG Frozen Metrics Specification
_Source: Grok 4.20 multi-agent session, 2026-03-19_
_Review notes: Claude Code session, 2026-03-19_
_Status: FINAL — implementation ready, all issues resolved_

---

## Overview

Frozen metrics for Be Still, Action Steps, and Exposition sections of the devotional
generator. All checks are pure Python (regex, set intersection, string operations).
No LLM, no API, no randomness. Same input → same score, always.

Core technique: **passage signature** extracted from the source scripture text for that day.
Computed once per day, used for all overlap checks across sections.

---

## Passage Signature Extraction

```python
def extract_signature(scripture_text: str):
    import re
    text = re.sub(r'[^a-zA-Z\s]', ' ', scripture_text.lower())
    words = text.split()

    # Single keywords — exclude stop words and single-char tokens
    keywords = {w for w in words if w not in STOP_WORDS and len(w) > 1}

    # Relaxed bigrams — include if AT LEAST ONE word is a content keyword
    # This preserves "lie down", "he makes", "shadow of death", "rod and staff", etc.
    relaxed_bigrams = {
        f"{words[i]} {words[i+1]}"
        for i in range(len(words) - 1)
        if (words[i] not in STOP_WORDS) or (words[i+1] not in STOP_WORDS)
    }

    # Strict bigrams — BOTH words are content keywords (used only for bonus tier)
    strict_bigrams = {
        f"{words[i]} {words[i+1]}"
        for i in range(len(words) - 1)
        if words[i] not in STOP_WORDS and words[i+1] not in STOP_WORDS
    }

    # Relaxed trigrams — at least TWO of three words are content keywords
    relaxed_trigrams = {
        f"{words[i]} {words[i+1]} {words[i+2]}"
        for i in range(len(words) - 2)
        if sum(w not in STOP_WORDS for w in words[i:i+3]) >= 2
    }

    passage_phrases = relaxed_bigrams | relaxed_trigrams  # main set for base checks
    return keywords, passage_phrases, strict_bigrams
```

**Why relaxed bigrams:** The strict "both words must be content" filter was dropping
"lie down", "he makes", "my shepherd", "shadow of death", "rod and staff", "goodness
and mercy", "paths of righteousness" — all meaningful passage phrases. The relaxed filter
(at least one content word) preserves them while still excluding pure filler like "and the"
or "in in". Strict bigrams are retained as a separate set for the high-quality bonus tier only.

---

## STOP_WORDS (frozen — do not modify without versioning)

**God, Lord, Jesus, Christ, Holy, Spirit are NOT stop words.** They carry theological
weight and vary in centrality across passages.

```python
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
```

---

## Proximity Helper

```python
def is_within_window(text: str, target_phrase: str, window_size: int = 15) -> bool:
    """Return True if '?' appears within ±window_size tokens of target_phrase."""
    tokens = text.lower().split()
    phrase_tokens = target_phrase.lower().split()
    phrase_len = len(phrase_tokens)
    for i in range(len(tokens) - phrase_len + 1):
        if tokens[i:i + phrase_len] == phrase_tokens:
            left = max(0, i - window_size)
            right = min(len(tokens), i + phrase_len + window_size)
            window_text = ''.join(tokens[left:right])
            if '?' in window_text:
                return True
    return False
```

---

## 1. Be Still Section Metric (0–100)

**Input:** `prompts: list[str]`, `scripture_text: str`

```python
passage_keywords, passage_phrases, strict_bigrams = extract_signature(scripture_text)
required_min = max(3, len(passage_keywords) // 3)
# Genesis 1:1 (~5 keywords) → need ≥3
# Psalm 23:1-6 (~12 keywords) → need ≥4
# Romans 8:1-17 (~20+ keywords) → need ≥6
```

### Required Base (0–60 pts)

| Check | Points |
|-------|--------|
| Keyword overlap ≥ `required_min` | +25 |
| Keyword overlap ≥ `required_min - 1` | +15 |
| Keyword overlap ≥ `required_min - 2` | +5 |
| At least one **relaxed bigram or trigram** appears anywhere in the section | +15 |
| At least one **individual prompt** contains both `?` AND a relaxed phrase (same prompt) | +20 |

For the bigram-in-question check: iterate individual prompts, not concatenated text.

### Template Penalties (subtract, floor at 0)

**–15 per match, max –60:**

```python
BE_STILL_TEMPLATE_PATTERNS = [
    r"concrete obedience that takes .{1,40} seriously rather than at a distance",
    r"scene of .{1,60} slowly and let it settle",
    r"faithful response to god.?s word",
    r"truthfulness under pressure",
    r"new allegiance demanded by",
    r"sit with .{1,40} for two quiet minutes",
]
```

### Bonus Points (0–40)

| Check | Points |
|-------|--------|
| At least one prompt: a **strict bigram** (both content words) inside a question (`is_within_window`) | +15 |
| Average prompt word count > 22 | +10 |
| At least one prompt: emotional/bodily keyword within ±15 tokens of a passage phrase | +15 |

Emotional/bodily pattern: `r"feel|heart|body|resist|rest|fear|trust|grieve|rejoice|ache|still|weight"`

### Score Calibration

| Range | Meaning |
|-------|---------|
| **0** | Current template output — all 4 penalty patterns fire simultaneously, wiping the base |
| **20–40** | Penalty patterns removed but no passage phrase engagement |
| **60–79** | Template clean, some passage phrases in questions |
| **80+** | Genuinely specific to this passage |
| **85–97** | Good human-written examples |

**Note:** Grok estimated 35–42 for current output assuming 2 penalty patterns fire.
Validated against actual Psalm 23 samples: all 4 patterns fire → score = 0.
The metric is more discriminating than predicted. This is correct behavior.

Pass ≥ 80 · Revise ≥ 60 · Fail < 60

---

## 2. Action Steps Section Metric (0–100)

**Input:** `connector: str`, `items: list[str]`, `scripture_text: str`

### Required Base (0–60 pts)

| Check | Points |
|-------|--------|
| Connector does NOT match template regex | +25 |
| ≥2 individual steps each contain ≥1 passage keyword OR relaxed phrase | +20 |
| Zero steps match meta-reading instruction patterns | +15 (all or nothing) |

**Connector template regex (–25 if matched):**
```python
r"because .{1,60} calls for concrete obedience that takes .{1,40} seriously rather than at a distance today"
```

**Meta-reading instruction patterns (–30 if any match):**
```python
ACTION_STEPS_META_PATTERNS = [
    r"write one sentence naming how",
    r"name one place where",
    r"pause and ask how .{1,60} should shape",
    r"how .{1,60} presses on",
]
```

### Additional Penalties (–15 per match, max –45)

```python
ACTION_STEPS_BOILERPLATE_PATTERNS = [
    r"concrete obedience",
    r"costly act of obedience",
    r"cross-shaped faithfulness",
    r"grateful obedience within god.?s generous boundaries",
]
```

### Bonus Points (0–40)

| Check | Points |
|-------|--------|
| At least one step contains a same-day tangible marker | +20 |
| At least one step framed as response to God's prior action (see pattern below) | +15 |
| Connector itself contains ≥1 relaxed phrase | +5 |

**Same-day tangible marker:**
```python
r"today|now|this morning|this evening|tell one person|write down|physically|call|send a message|before you"
```

**Grace-response framing:** within one step, `because|since|therefore` within ±10 tokens of
`god has|christ has|the lord|mercy|grace`, AND the step also contains a passage keyword.

### Score Calibration

| Range | Meaning |
|-------|---------|
| **0** | Current template output — connector template + meta steps + boilerplate penalties dominate |
| **20–40** | Connector fixed, boilerplate removed, steps still vague |
| **60–79** | Passage keywords present, not yet concrete/same-day |
| **80+** | Specific, passage-rooted, same-day actionable |
| **85–97** | Good human-written examples |

Pass ≥ 80 · Revise ≥ 60 · Fail < 60

---

## 3. Exposition Metric (0–100)

**Input:** `text: str`, `scripture_text: str`

| Check | Points |
|-------|--------|
| Word count 280–550 | +20 |
| ≥1 direct quote OR 5+ word verbatim sequence from the passage | +20 |
| ≥1 Reformed theological concept from `REFORMED_CONCEPTS` | +20 |
| No forbidden boilerplate | +10 |
| No sentence fragments (all sentences 8–70 words ending in `.?!`) | +10 |
| ≥3 unique passage keywords each appear ≥1 time | +20 |

**Obsessive repetition penalty:** Any 2–3 word phrase appearing >4 times → –10

```python
REFORMED_CONCEPTS = frozenset({
    "grace", "justification", "sanctification", "covenant", "election", "atonement",
    "sovereignty", "providence", "imputation", "adoption", "perseverance",
    "union with christ", "regeneration", "repentance", "propitiation", "reconciliation",
    "redemption", "intercession", "glorification", "total depravity", "calling",
    "resurrection",
})

EXPOSITION_BOILERPLATE_PATTERNS = [
    r"opens with a scene marked by",
    r"worship and wisdom under the word of god",
    r"must be received before it is applied",
    r"the passage puts one clear scene in front of us",
]
```

---

## Implementation Location

**File:** `src/autoresearch/frozen_metrics.py`

**Public API:**
```python
def score_be_still(prompts: list[str], scripture_text: str) -> dict
def score_action_steps(connector: str, items: list[str], scripture_text: str) -> dict
def score_exposition(text: str, scripture_text: str) -> dict
```

**Return structure (all three functions):**
```python
{
    "score": int,                    # 0–100
    "components": dict,              # check name → points earned/lost
    "penalties_applied": list[str],  # which penalty patterns fired
    "bonuses_applied": list[str],    # which bonus checks passed
}
```

Log `components`, `penalties_applied`, and `bonuses_applied` to the experiment store
`metrics` field. This gives the LLM trainer a precise breakdown so it can propose a
targeted fix rather than a generic suggestion.

---

## How These Plug Into the Training Loop

```
Generate section output
    ↓
score_be_still(prompts, scripture_text)
    → {"score": 38, "penalties": ["sit with ... for two quiet minutes"], "bonuses": [], ...}
    ↓
If score < 80:
    LLM trainer receives: score + full components breakdown + which penalties fired
    LLM proposes ONE specific, concrete change (template code, generation logic, or prompt)
    Apply change
    score_be_still(...) again → new score
    new_score > old_score → keep, log "improved +N pts"
    new_score <= old_score → reject, log "no improvement"
    ↓
After 50 experiments: gate review checks score trend (delta over time, not LLM judgment)
```

**The frozen score is the only judge. The LLM proposes. The score decides.**

---

## Validation Test (run immediately after implementing)

Score the three Psalm 23 sample days (stored in
`outputs/devotionals/2026-03-17__145553__trusting-god-in-uncertainty__3-day__vol-1__book.json`).

Expected results with relaxed bigrams:
- Be Still: **35–42** per day (up from strict-filter estimate of 12–28)
- Action Steps: **15–22** per day (unchanged — penalties dominate)

If Be Still scores land outside 30–50, the `required_min` proportional floor or
bigram relaxation needs recalibration before training restarts.

---

## 4. Apply-Change Mechanism (JSON Config + JSON Patch)

Move every hardcoded template string, connector skeleton, forbidden-phrase list, and prompt
skeleton out of Python worker code into a single runtime config file:

```
templates/worker_config.json
```

```json
{
  "be_still": {
    "prompt_1_template": "...",
    "prompt_2_starter": "...",
    "forbidden_phrases": ["concrete obedience that takes .* seriously ...", "..."]
  },
  "action_steps": {
    "connector_template": "...",
    "meta_step_forbidden": ["write one sentence naming how", "..."]
  },
  "exposition": { "...": "..." }
}
```

Worker code becomes **purely data-driven** — reads config at runtime, no hardcoded strings.

When frozen metric scores below threshold, the LLM proposer receives:

```
Output ONLY a valid JSON Patch (RFC 6902) that modifies worker_config.json.
No other text. Example: [{"op": "replace", "path": "/be_still/prompt_2_starter", "value": "..."}]
Recent failed attempts: {summary of last 10}
Current score: {score} — components: {breakdown}
Propose something structurally different from all previous attempts.
```

Training loop applies the patch, rescores, keeps or rolls back atomically:

```python
patch = json.loads(llm_proposal)
backup = copy.deepcopy(config)
jsonpatch.apply_patch(config, patch)   # pip install jsonpatch
save_config(config)
new_score = score_be_still(...)
if new_score > old_score:
    git_commit("auto: improved Be Still templates")
else:
    restore(backup)  # rollback
```

Every accepted patch goes into git history. Never let the LLM output raw Python code.

---

## 5. Anti-Repetition / Novelty Gate

Append-only proposal ledger at `experiments/proposal_ledger.jsonl`. Each line:
```json
{"proposal_hash": "sha256...", "patch": [...], "score_before": 42, "score_after": 67, "timestamp": "..."}
```

Deterministic novelty check (no LLM judgment):

```python
import hashlib, difflib, json

def is_novel(proposed_patch: list, ledger_path: str, similarity_threshold: float = 0.85) -> bool:
    current_hash = hashlib.sha256(
        json.dumps(proposed_patch, sort_keys=True).encode()
    ).hexdigest()
    try:
        lines = open(ledger_path).readlines()[-50:]
    except FileNotFoundError:
        return True
    for line in reversed(lines):
        entry = json.loads(line)
        if entry["proposal_hash"] == current_hash:
            return False  # exact duplicate
        sim = difflib.SequenceMatcher(
            None,
            json.dumps(proposed_patch, sort_keys=True),
            json.dumps(entry["patch"], sort_keys=True),
        ).ratio()
        if sim > similarity_threshold:
            return False
    return True
```

In the loop: if `not is_novel(patch, ledger)` → auto-reject, log "duplicate rejected", continue.

Feed the LLM a compact summary of the last 10–20 experiments in its prompt so it has
context to propose something different. The hash + similarity gate enforces it structurally.

---

## 6. Outliner Frozen Metric

The outliner outputs structured JSON. Force it with:

```
Output ONLY valid JSON:
{"days": [{"day": 1, "range": "Psalm 23:1-2"}, ...]}
```

Scoring function:

```python
def score_outline(outline_text: str, input_ref: str, num_days: int, full_scripture_text: str) -> dict:
    score = 0

    # Structure (40 pts)
    days = try_parse_outline_json(outline_text)        # returns list or None
    if days is not None:
        score += 20
    if days and len(days) == num_days:
        score += 20

    # Coverage & validity (40 pts)
    if days and ranges_are_sequential_and_non_overlapping(days, input_ref):
        score += 20
    if days and total_verses_covered(days) == total_verses_in(full_scripture_text):
        score += 20

    # Even distribution (20 pts)
    if days and distribution_is_balanced(days, tolerance=0.15):
        score += 20

    # Penalties
    if days and any(day_has_zero_verses(d) for d in days):
        score -= 30
    if days and any(range_format_invalid(d["range"]) for d in days):
        score -= 20

    return {"score": max(0, score), "days_parsed": len(days) if days else 0}
```

**What this catches:** exact day count, no gaps/overlaps, full coverage, parseable structure,
even distribution. **What it deliberately does not judge:** theological quality of splits or
whether the outline "feels pastoral" — those are human spot-checks at gate reviews.

Pass ≥ 80 · Revise ≥ 60 · Fail < 60

---

## Summary: Full Training Loop (all pieces in place)

```
1. Load worker_config.json
2. Generate section output using config
3. Run frozen metric → score + components breakdown
4. If score >= 80: log pass, continue
5. If score < 80:
   a. Build LLM prompt: score + breakdown + last 10 experiment summaries
   b. LLM outputs JSON Patch proposal
   c. is_novel(patch, ledger)? → if not: log "duplicate rejected", goto 2
   d. Apply patch to config
   e. Regenerate section, score again
   f. new_score > old_score? → keep patch, git commit, log improvement
      otherwise → rollback config, log "no improvement"
6. Every 50 experiments: gate review checks score trend (delta over time)
```

The LLM never judges success. The frozen score judges. Every accepted change is in git.
Every proposal is in the ledger. The loop runs unsupervised.

---

_References:_
_• `docs/system/autoresearch-architecture-reset.md` — why training was stopped_
_• `docs/system/local-llm-architecture-plan.md` — Ollama / local LLM infrastructure_
_• `docs/system/ai-brainstorm-prompt.md` — full system briefing for external AI sessions_
