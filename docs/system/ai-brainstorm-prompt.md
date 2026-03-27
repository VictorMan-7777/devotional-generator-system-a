# DevG Frozen Metrics Brainstorm — Prompt for External AI Sessions
_Created: 2026-03-19. Self-contained. No repo access required._

---

## Who This Is For

This document is a complete briefing for an AI assistant (Grok, ChatGPT, Gemini, Claude, etc.)
being asked to help brainstorm **frozen, deterministic quality metrics** for a devotional
content generator. The system owner will paste this into a fresh session and ask for input.

You do not need access to any codebase. Everything you need is in this document.

---

## What the System Is

**DevG** is a software system that generates multi-day Reformed evangelical devotional books.
Given a scripture passage (e.g., "Psalm 23", "Ruth 1-4") and a day count (6, 12, 18, 30 days),
it produces a complete devotional with one entry per day. Each day has five sections:

1. **Exposition** — ~300–500 words of expository commentary on the day's passage
2. **Be Still** — 3 contemplative prompts inviting the reader into quiet reflection
3. **Action Steps** — a connector phrase + 2–3 concrete steps for the reader to take today
4. **Prayer** — a short closing prayer
5. **Timeless Wisdom** — a historical quote from a theologian (pre-1952)

The target reader is an adult Protestant Christian with some Bible literacy. Tone is pastoral,
Reformed, and serious — not therapeutic or self-help. Think Spurgeon devotional, not Joel Osteen.

---

## The Problem We Are Trying to Solve

The system has an automated training loop that runs these workers and tries to improve their
output over time. After 600+ training cycles, there has been **zero measurable improvement**
in the Be Still and Action Steps sections, and only marginal improvement in Exposition.

The root cause: **there is no frozen metric**. The training loop uses an LLM to evaluate
the output of another LLM (or a deterministic template). LLM-judged quality drifts — the
evaluator is as subjective as the worker. The loop optimizes for "satisfying the reviewer"
rather than "producing better content."

The fix requires defining a **frozen metric** for each section: a deterministic scoring
function (Python code) that produces the same score every time given the same input,
requires no LLM to run, and genuinely measures whether the content is better or worse.

This is what we need your help brainstorming.

---

## Real Sample Output

These three days were generated from Psalm 23. Read them carefully — they reveal
the exact quality problems the metrics need to catch.

---

### DAY 1 — Psalm 23:1-2

**Exposition:**
> Psalm 23:1-2 opens with a scene marked by faithful response to God's word. The text does
> not ask the reader to admire the moment from a distance. The passage puts one clear scene
> in front of us: He makes me lie down in green pastures. We should stay with that scene
> before we rush to a slogan. What the passage shows through makes, lie, down must be received
> before it is applied. That keeps the reading honest. worship and wisdom under the word of god.
> Psalm 23:1-2 stays concrete through The Lord the Psalmist's Shepherd — the specific language
> of makes, lie, down does the work before any principle...

**Be Still:**
- Sit with Psalm 23:1-2 for two quiet minutes. Read the scene of faithful response to God's word slowly and let it settle before you move on.
- Where does this passage call for concrete obedience that takes *makes* and *down* seriously rather than at a distance today?
- Stay for one more minute and answer God with one honest sentence of trust, repentance, or gratitude before continuing.

**Action Steps:**
Connector: *Because Psalm 23:1-2 calls for concrete obedience that takes makes and down seriously rather than at a distance today:*
- Write one sentence naming how Psalm 23:1-2 presses on the scene of He makes me lie down in green pastures.
- Name one place where concrete obedience that takes makes and down seriously rather than at a distance should change the way you listen, speak, or act today.

---

### DAY 2 — Psalm 23:3-4

**Exposition:**
> Psalm 23:3-4 opens with a scene marked by truthfulness under pressure. The text brings
> costly obedience into view and refuses every attempt to make sacrifice feel decorative.
> The passage puts one clear scene in front of us: He guides me in the paths of righteousness
> For His name's sake. We should stay with that scene before we rush to a slogan. What the
> passage shows through guides, paths, righteousness must be received before it is applied.
> That keeps the reading honest. worship and wisdom under the word of god centered on guides
> paths righteousness his name...

**Be Still:**
- Sit with Psalm 23:3-4 for two quiet minutes. Read the scene of truthfulness under pressure slowly and let it settle before you move on.
- Where does this passage call for concrete obedience that takes *guides* and *paths* seriously rather than at a distance today?
- Stay for one more minute and answer God with one honest sentence of confession, courage, or repentance before continuing.

**Action Steps:**
Connector: *Because Psalm 23:3-4 calls for concrete obedience that takes guides and paths seriously rather than at a distance today:*
- Name one costly act of obedience that Psalm 23:3-4 places before you today.
- Accept one inconvenience without complaint as a small act of cross-shaped faithfulness.

---

### DAY 3 — Psalm 23:5-6

**Exposition:**
> Psalm 23:5-6 opens with a scene marked by new allegiance demanded by Christ's presence.
> The text does not ask the reader to admire the moment from a distance. The passage puts
> one clear scene in front of us: Surely goodness and lovingkindness will follow me all the
> days of my life. We should stay with that scene before we rush to a slogan. What the passage
> shows through surely, goodness, lovingkindness must be received before it is applied.
> That keeps the reading honest. watchful surrender before costly obedience...

**Be Still:**
- Sit with Psalm 23:5-6 for two quiet minutes. Read the scene of new allegiance demanded by Christ's presence slowly and let it settle before you move on.
- Where does this passage call for grateful obedience within God's generous boundaries today?
- Stay for one more minute and answer God with one honest sentence of trust, repentance, or gratitude before continuing.

**Action Steps:**
Connector: *Because Psalm 23:5-6 calls for grateful obedience within God's generous boundaries today:*
- Before your next decision, pause and ask how Psalm 23:5-6 should shape your response.
- Offer one concrete act of service that matches the patience or steadiness this passage commends.

---

## What Is Clearly Wrong (Diagnose Before Prescribing Metrics)

Read the samples above and notice:

### Exposition problems
- Sentence 1 is always the same template: "[Reference] opens with a scene marked by [X]."
- The phrase "worship and wisdom under the word of god" appears verbatim in all three days — it is a hardcoded template fragment leaking into the output
- The exposition extracts 2–3 key words from the verse and repeats them obsessively ("makes, lie, down") rather than explaining the passage
- Sentences cut off mid-thought (template truncation artifact)
- No real theological content — no commentary tradition drawn on, no cross-references, no doctrine named

### Be Still problems
- Prompt 1 is identical in structure across all days: "Sit with [X] for two quiet minutes. Read the scene of [phrase] slowly and let it settle before you move on."
- Prompt 2 is a fill-in-the-blank template: "Where does this passage call for concrete obedience that takes [word1] and [word2] seriously rather than at a distance today?"
- Prompt 3 is always a variant of: "Stay for one more minute and answer God with one honest sentence of [X] before continuing."
- None of the prompts are specific to what Psalm 23 actually says — they could belong to any passage

### Action Steps problems
- The connector phrase is generated by the same formula every time: "Because [reference] calls for concrete obedience that takes [word1] and [word2] seriously rather than at a distance today:"
- Step 1 often instructs the reader to "write one sentence naming how [passage] presses on [verse]" — this is a meta-instruction about reading, not a real action step
- Steps could appear in any devotional for any passage
- No step is specific enough to be attempted today in a concrete way

---

## What Good Looks Like (Human Standard)

A **good Be Still section** for Psalm 23:1-2 might look like:
- "The shepherd *makes* the sheep lie down — the sheep does not choose the rest. Where are you resisting rest that God is actively providing for you right now?"
- "Green pastures and still waters suggest abundance and peace, not urgency. What does it feel like in your body right now to sit in that image for sixty seconds?"
- "The psalm opens with 'The Lord is my shepherd' — a statement of ownership and care. Is that a settled conviction or a hopeful wish for you today?"

These are **passage-specific**. They use the actual imagery of Psalm 23. They cannot be
swapped into a devotional on Romans 8 or Revelation 3 without becoming wrong.

A **good Action Steps section** for Psalm 23:1-2 might look like:
- Connector: *The shepherd provides rest you did not ask for and may not feel you deserve. Because of that:*
- "Identify one area of life where you have been striving rather than resting. Write it down and physically put the paper somewhere visible."
- "Tell one person today something specific you are grateful for — name the exact thing, not a general blessing."

These steps are **today-specific**, **concrete**, and **flow from the passage's own images**
(the shepherd providing rest, green pastures as gift).

---

## The Core Question

We need to define **frozen metrics** — scoring criteria a Python function can evaluate
without calling any LLM. The function receives the generated text and the source scripture
text, and returns a score between 0 and 100.

The key constraint: **the metric must be deterministic**. Same input, same score, every time.
No LLM involved. This is what makes it a "frozen" evaluator that the training loop can
trust as ground truth.

### Questions to help you think about this:

**For Be Still:**
- What words or phrases from the source scripture verse should appear in at least one prompt?
- What structural patterns indicate a generic (bad) prompt vs. a specific (good) one?
- How do you detect "could appear in any devotional" programmatically?
- Is there a negative word list ("concrete obedience", "at a distance", "seriously") that indicates template leakage?

**For Action Steps:**
- What makes a step "same-day applicable"? Can that be tested with string patterns?
- What distinguishes "write one sentence naming how..." (meta-instruction) from a real action?
- Should at least one step contain a noun that also appears in the source scripture text?
- Can you detect the connector phrase formula by looking for the repeated template string?

**For Exposition:**
- Word count (too short = fail)?
- Presence of repeated boilerplate phrases = automatic deduction?
- At least one named theological concept (grace, covenant, atonement, sanctification, etc.)?
- Absence of sentence fragments or truncated mid-thoughts?
- The source verse text should appear at least once, quoted or closely paraphrased?

---

## Constraints on Your Answer

1. **No LLM at evaluation time.** The metric must be pure Python: string matching,
   regex, word lists, character counts, vocabulary intersection. No API calls.

2. **Deterministic.** Same text in → same score out. Always.

3. **Calibrated.** A score of 80 should mean something real. Not "the LLM liked it" but
   "it passed X out of Y checkable criteria."

4. **Trainable.** The metric needs to be improvable. If the system scores 52 today and 67
   next week, that delta should reflect genuine quality improvement, not noise.

5. **Not gameable in ways that don't improve quality.** A metric that rewards "uses more
   words from the verse" might cause the system to just stuff the verse into every sentence.
   Think about failure modes.

---

## Additional Context: The Training Architecture

The system will work like this once the frozen metrics are defined:

```
Generate output
    ↓
Run frozen metric → score
    ↓
If score < threshold:
    LLM proposes a specific change (to template, to prompt, to logic)
    Apply the change
    Run frozen metric again → new score
    If new score > old score: keep change
    If not: reject change, log failure
    ↓
Log everything to experiment ledger
```

The LLM's only job is to **propose changes**. It never judges whether the change worked.
Only the frozen metric judges. This is the pattern from the AutoResearch literature that
produces ~10% improvement in 50–100 experiments.

---

## What the System Owner Wants From You

1. **Suggest specific frozen metrics** for Be Still and Action Steps (Exposition is a bonus).
   Be concrete — "check if at least 2 words from the verse text appear in the prompts"
   is actionable. "Ensure theological depth" is not.

2. **Identify failure modes** in the metrics you suggest. What could game the score
   without actually improving the content?

3. **Suggest a score structure** — what does 0, 50, 80, 100 look like for each metric?
   What criteria are required vs. bonus?

4. **Flag any criteria that genuinely require human judgment** and cannot be automated.
   It is better to have a narrower frozen metric that is truly deterministic than a broader
   one that secretly requires LLM interpretation.

---

## One More Thing: What "Reformed Evangelical" Means for Content

This context matters for the metrics because it shapes what "good" means:

- **Scripture is the authority.** Content should point back to the text, not use the text
  as a springboard to general spirituality.
- **Grace, not self-improvement.** Action steps should be responses to what God has done,
  not instructions for becoming a better person through effort.
- **Specific obedience.** The Reformed tradition emphasizes concrete response to the Word —
  not vague spiritual dispositions but named, dateable acts of obedience.
- **Pastoral tone.** The reader is assumed to be a struggling believer, not a spiritual
  athlete. Steps should be achievable today, not aspirational over time.
- **The Be Still → Action arc.** The devotional has a deliberate flow: encounter God in
  stillness (Be Still), then respond with action (Action Steps). The action steps must
  flow from the stillness encounter, not from the exposition. This is a structural requirement.

---

_End of briefing. You now have everything needed to discuss frozen metrics for this system._
