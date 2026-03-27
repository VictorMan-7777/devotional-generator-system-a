# Competition AC Coverage Tracker

**Source:** PRD v16 Section 11 — Acceptance Criteria (authoritative, read-only)
**Updated:** 2026-03-25
**Purpose:** Track which ACs are covered by training, which are deterministic, and where gaps remain that block competition readiness.

All 43 ACs must pass for a devotional unit to be publication-ready.

---

## AC Coverage by Section

### Exposition (AC-01 through AC-11)

| AC | Criterion | Coverage | Status |
|---|---|---|---|
| AC-01 | Four-paragraph structure: opening declaration → historical context → theological unpacking → experiential bridge | Exposition TA active | 🔴 ~11% pass rate |
| AC-02 | Opening paragraph: one controlling idea as declarative theological claim | Exposition TA active | 🔴 ~11% pass rate |
| AC-03 | Context paragraph: literary and theological purpose within canonical setting | Exposition TA active | 🔴 Critical — mentioned as competition disqualifier |
| AC-04 | Theological paragraph: definition → close reading → inline cross-reference → character of God → summary | Exposition TA active | 🔴 ~11% pass rate |
| AC-05 | All doctrinal claims supported by passage or immediate canonical context | Exposition TA + Theological Reviewer | 🔴 Critical — mentioned as competition disqualifier |
| AC-06 | Experiential bridge opens with named contemporary cultural tension | Exposition TA active | 🔴 ~11% pass rate |
| AC-07 | Bridge grounds application in work of Christ or character of God | Exposition TA + Theological Reviewer | 🔴 ~11% pass rate |
| AC-08 | Bridge closes by creating felt need, not resolving tension | Exposition TA active | 🔴 ~11% pass rate |
| AC-09 | Communal voice (we/us/our) throughout | Deterministic validator (`exposition.py`) | 🟡 Validator exists; not connected to training logging |
| AC-10 | 500–700 words | Deterministic validator (`exposition.py`) | 🟡 Validator exists; not connected to training logging |
| AC-11 | Literary genre governs handling | Exposition TA + Theological Reviewer | 🔴 ~11% pass rate — Hebrews epistolary genre critical |

### Be Still (AC-12 through AC-17)

| AC | Criterion | Coverage | Status |
|---|---|---|---|
| AC-12 | 3–5 prompts | Deterministic validator (`be_still.py`) | 🟡 Validator exists; ~28% training pass rate |
| AC-13 | First prompt directs to stillness and receptivity | Be Still TA active | 🟡 ~28% pass rate |
| AC-14 | Prompts move inward to outward | Be Still TA active | 🟡 ~28% pass rate |
| AC-15 | Final prompt creates felt need flowing into Action Steps | Be Still TA active | 🟡 ~28% pass rate |
| AC-16 | Second-person voice | Deterministic validator (`be_still.py`) | 🟡 Validator exists |
| AC-17 | Prompts arise from Exposition — no new concepts | Be Still TA active | 🟡 ~28% pass rate |

### Action Steps (AC-18 through AC-20b)

| AC | Criterion | Coverage | Status |
|---|---|---|---|
| AC-18 | Opens with connector phrase referencing Be Still | Deterministic validator (`action_steps.py`) | 🟡 ~50% pass rate — closest to gate |
| AC-19 | 1–3 specific, same-day applicable items grounded in passage | Action Steps TA active | 🟡 ~50% pass rate |
| AC-20a | Active expectation and partnership with God — not passive compliance | Action Steps TA active | 🟡 ~50% pass rate |
| AC-20b | At least one step acknowledges unfamiliarity grounded in God's faithfulness | Action Steps TA active | 🟡 ~50% pass rate |

### Prayer (AC-21 through AC-32)

| AC | Criterion | Coverage | Status |
|---|---|---|---|
| AC-21 | Addressed to named person of Trinity | **NO TRAINER AGENT** | 🔴 CRITICAL GAP |
| AC-22 | Opens naming specific attribute/action of God from passage | **NO TRAINER AGENT** | 🔴 CRITICAL GAP |
| AC-23 | Names human condition passage exposes | **NO TRAINER AGENT** | 🔴 CRITICAL GAP |
| AC-24 | Echoes language of Scripture passage | **NO TRAINER AGENT** | 🔴 CRITICAL GAP |
| AC-25 | Petition traceable to specific verse/phrase — not merely thematically adjacent | **NO TRAINER AGENT** | 🔴 CRITICAL GAP |
| AC-26 | Sounds like laying hold of God's willingness — no pleading/bargaining language | **NO TRAINER AGENT** | 🔴 CRITICAL GAP |
| AC-27 | Prayer Trace Map complete — every petition maps to specific verse, exposition sentence, or Be Still prompt | Deterministic validator (`prayer.py`) | 🔴 Validator exists; no trainer uses it |
| AC-28 | Closes with trust or surrender | **NO TRAINER AGENT** | 🔴 CRITICAL GAP |
| AC-29 | Theologically literate reader could ID passage from prayer alone | **NO TRAINER AGENT** | 🔴 CRITICAL GAP |
| AC-30 | One cohesive unit with discernible arc | **NO TRAINER AGENT** | 🔴 CRITICAL GAP |
| AC-31 | 120–200 words | Deterministic validator (`prayer.py`) | 🔴 Validator exists; no trainer uses it |
| AC-32 | No content contradicting doctrinal guardrails | Theological Reviewer (partial) | 🔴 Not systematically enforced in training |

### Infrastructure / Pipeline (AC-33 through AC-43)

| AC | Criterion | Coverage | Status |
|---|---|---|---|
| AC-33 | Validator pass on all criteria | All training agents (partial) | 🟡 Not connected to AC logging |
| AC-34 | Verified Turabian attribution, `public_domain=true`, block quote + footnote | **NO QUOTE TRAINER** | 🔴 Gap |
| AC-35 | Scripture rendered as block quote | PDF Layout Engineer (deterministic) | 🟢 Deterministic; PDF graduated |
| AC-36 | Scripture text successfully retrieved and validated | Scripture Retrieval (deterministic) | 🟢 Deterministic |
| AC-37 | All sections `approval_status = approved` before export | Export Gate (deterministic) | 🟢 Deterministic |
| AC-38 | PDF passes all KDP compliance checks | PDF Training Agent | 🟢 PDF graduated |
| AC-39 | Quote de-duplication passed | Pipeline (deterministic) + Quote Catalog | 🟡 Partial — no quote trainer |
| AC-40 | Author diversity report reviewed by operator | **REPORT NOT IMPLEMENTED** | 🔴 Gap |
| AC-41 | Day 6 sending prompt: 40–80 words, names theme, open question, approved | **NO DAY 6/7 TRAINER** | ⚪ Optional (Day 7 not enabled) |
| AC-42 | Day 7 page: Before/After service, Track A/B, 120–180 words After | **NO DAY 6/7 TRAINER** | ⚪ Optional (Day 7 not enabled) |
| AC-43 | Sunday Worship Integration: 150–250 words, convergence/divergence | **NO DAY 6/7 TRAINER** | ⚪ Optional (Day 7 not enabled) |

---

## Competition-Critical Gaps (must close before Stage 4)

### Gap 1 — Prayer Trainer Agent (AC-21 through AC-32)
**Impact:** Prayer is 12 ACs with no trainer. ~40% pass rate but no AC-level evaluation.
**What's needed:** Prayer trainer must evaluate against AC-21 through AC-32 explicitly.
**AC scoring directive:** Posted to Grok in `grok_workspace/notifications/ac_scoring_design_directive.md` — awaiting proposal.

### Gap 2 — AC Scoring Not Connected to Training Logs
**Impact:** Workers train but experiments don't log AC pass/fail. We cannot query per-AC pass rates.
**What's needed:** `ac_scorer.py` module feeding into `log_experiment()` metrics.
**Owner:** Grok (proposal), Claude (apply).

### Gap 3 — AC-03 and AC-05 in Exposition (competition disqualifiers)
**Impact:** AC-03 (canonical context) and AC-05 (doctrinal claims supported by passage) are flagged in Stage 4 gate as disqualifying. Exposition ~11% pass rate suggests these fail frequently.
**What's needed:** Stage 3 exposition training with explicit AC-03 and AC-05 focus on epistolary/argumentative passages.

### Gap 4 — AC-34 Quote Attribution
**Impact:** Every day must carry verified Turabian attribution with `public_domain=true`.
**What's needed:** Verify quote catalog has correct attribution fields. No trainer needed if pipeline enforces it deterministically.

### Gap 5 — AC-40 Author Diversity Report
**Impact:** Report not implemented. Operator cannot review what doesn't exist.
**What's needed:** Either implement the report generator or document that it will be produced manually at gate time.

---

## Hebrews-Specific AC Risk Map

For competition submission on Hebrews 1-10:

| AC | Hebrews-Specific Risk | Priority |
|---|---|---|
| AC-05 | Epistolary doctrine — every claim must derive from Hebrews argument, not imported themes | **Critical** |
| AC-07 | Bridge must ground in atonement (Hebrews' Christological argument) — not generic application | **Critical** |
| AC-11 | Epistolary genre governs — Hebrews is not narrative; must not use narrative template | **Critical** |
| AC-22 | Prayer must name a specific Hebrews attribute (high priestly, once-for-all, etc.) | High |
| AC-25 | Prayer petition traceable to specific Hebrews verse — not generic NT piety | High |
| AC-29 | Theologically literate reader can ID Hebrews from prayer — not generic epistle | High |
| AC-03 | Context must identify cumulative argument function within Hebrews argument arc | High |

---

## AC Coverage Summary

| Section | ACs | 🟢 Covered | 🟡 Partial | 🔴 Gap | ⚪ Optional |
|---|---|---|---|---|---|
| Exposition | 11 | 0 | 3 | 8 | 0 |
| Be Still | 6 | 0 | 6 | 0 | 0 |
| Action Steps | 4 | 0 | 4 | 0 | 0 |
| Prayer | 12 | 0 | 0 | 12 | 0 |
| Infrastructure | 10 | 4 | 2 | 2 | 3 |
| **Total** | **43** | **4** | **15** | **22** | **3** |

**Of the 40 non-optional ACs, only 4 are fully covered. 22 have active gaps.**

---

## Action Items for Stage 3

1. **Grok:** Deliver AC scorer proposal (`ac_scorer.py`) — connects existing validators to training log metrics. Directive already posted. No further design session needed; `src/validation/` validators are the implementation base.

2. **Grok:** Prayer trainer must evaluate AC-21 through AC-32 explicitly during Stage 3 training. Current prayer training targets burden/fallback — not AC compliance. Redirect.

3. **Claude:** Apply AC scorer once proposal arrives (Option C — Grok proposes, Claude applies).

4. **Stage 4 gate:** Before running Stage 4 Hebrews dispatch, confirm AC scoring is live in training logs so the gate results are AC-verifiable, not just trainer-score-based.
