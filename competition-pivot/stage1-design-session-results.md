# Stage 1 Design Session Results

**Date:** 2026-03-25
**Status:** Both trainers APPROVED WITH CONDITIONS — Grok to revise and submit proposal

---

## Theological Reviewer — APPROVED WITH CONDITIONS

### Domain answers:
1. **Warning passage classification:** "Cumulative Argument with embedded exhortation" covers it — but only if "embedded" means full antecedent enforcement applies to warning days. No softer enforcement path.
2. **Theological vs. structural classification conflicts:** Function governs over surface grammar. Heb 5:11–6:12 and 10:26–31 look like exhortation on the surface but function as cumulative argument beats. Classifier must receive surrounding argument context, not classify days in isolation.
3. **Warning "structural beat" — specific day slot vs. text-driven:** Text-driven. Do NOT hard-code slot positions. Template detects and positions based on text. Same antecedent test applies before AND after warning day.
4. **Week 3 mid-week warning:** No special "mid-week warning slot" schema element needed. The warning days are Move 2 of 3 in Week 3's required sequence. Antecedent must be writable TO the warning AND FROM the warning to Melchizedek. Template must not allow skipping 5:11–6:12 to jump straight to 7:1ff — that is SF-4.

### Conditions (all required before proposal is written):
1. **Classifier context requirement:** Proposal must specify how passage-context is passed to the classifier. Classifying days in isolation will systematically misclassify warning passages.
2. **Full antecedent enforcement on warning days:** Proposal must explicitly state warning-passage days get the same Day N→Day N+1 antecedent check as every other day. No implicit softer path.
3. **`warning_slot` field must be defined operationally:** Not just a flag — must enforce that antecedent sentences are writable from preceding day TO this day AND from this day TO following day.
4. **Hard-fail on warning passage routing:** If warning passage is being routed to Ethical-Didactic template or positioned as application day, template must HARD FAIL. Not flag. SF-4 and SD-2 are non-negotiable.

---

## Outliner Trainer — APPROVED WITH CONDITIONS

### Domain answers:

**Required JSON schema (authoritative — no substitutions):**
```json
{
  "week_opening_tension": "<question or tension that Day 1 opens>",
  "week_closing_location": "<where Day 5 lands in the argument>",
  "days": [
    {
      "day_subtype": "argument_step" | "warning_beat" | "exhortation",
      "arg_step_index": <int — sequential, null if warning/exhortation>,
      "logical_antecedent": "<Because we established X, today we address Y>",
      "arg_advance_claim": "<what new argumentative ground this day covers>",
      "warning_slot": <bool>,
      "warning_position": "mid_week" | "end_of_week" | null
    }
  ],
  "week_to_week_bridge": "<premise this week's conclusion provides to next week, null for Week 5>",
  "stakes_level": <int 1-5 — must escalate Week 1 to Week 5>
}
```

**Progression enforcement (mechanical, not qualitative):**
- `logical_antecedent` must be non-empty and non-generic on every Day 2–5 — HARD FAIL if not
- `arg_step_index` strictly increasing within week across argument-step days — HARD FAIL if not
- `week_closing_location` ≠ `week_opening_tension` — HARD FAIL if semantically equivalent
- Warning beats do NOT increment `arg_step_index`
- No percentage threshold — every argument-step day must advance, binary per day

**Multi-week tracking:** `week_to_week_bridge` field. Week N+1 opening must be downstream of Week N bridge. Required field; automated validation in Stage 2.

**Hard fail vs. flag:**
- HARD FAIL: empty/generic `logical_antecedent`, non-increasing `arg_step_index`, warning passage textually present but `day_subtype` not `warning_beat`
- FLAG: similar (not identical) `week_closing_location`/`week_opening_tension`, non-obvious `week_to_week_bridge`

**Classifier:** Must run on deterministic path by default. Hebrews weekly type assignments may be hard-coded as ground truth — this is correct, not cheating. LLM classification permitted as enhancement for unknown passages only.

**Scope:** Classifier scoped to Hebrews and existing harness passage types only. Do not attempt to solve Luke 15/Romans/Ezekiel classifier problems in Stage 1.

### Conditions (all required before proposal is written):
1. **Schema as specified above — exactly.** No substitutions. Raise conflicts with Outliner Trainer before submission.
2. **Week-turn signal conflict identification.** Proposal must explicitly state how `PASSAGE_FOCUS 'week turn'` interacts with `week_to_week_bridge`. Resolve any conflict in the proposal.
3. **Classifier scope limited to Stage 1 target.** No scope creep.
4. **Hard fail conditions implemented as specified.** Not downgradeable to advisory flags without Outliner Trainer explicit approval.
5. **`warning_position` field distinguishes `mid_week` / `end_of_week` / `null`.** Required. Non-negotiable.
6. **Harness coverage confirmation.** Proposal must list which harness passages cover each of the 5 Hebrews weeks. Add entries if coverage gaps exist.

---

## Consolidated Conditions for Grok's Proposal

Before any code is written, the proposal must explicitly address:

| # | Condition | Domain |
|---|---|---|
| C1 | Classifier receives argument context, not day-in-isolation | Theological |
| C2 | Warning-passage days get full antecedent enforcement | Theological |
| C3 | `warning_slot` enforces antecedent both before and after warning day | Theological |
| C4 | Hard-fail on warning passage routed to Ethical-Didactic or application slot | Theological |
| C5 | JSON schema matches Outliner Trainer spec exactly | Structural |
| C6 | Week-turn signal / `week_to_week_bridge` conflict identified and resolved | Structural |
| C7 | Classifier scope: Hebrews + existing harness types only, no scope creep | Structural |
| C8 | Hard fail conditions implemented as hard fails, not downgraded | Structural |
| C9 | `warning_position` field: `mid_week` / `end_of_week` / `null` | Structural |
| C10 | Harness coverage confirmed for all 5 Hebrews weeks | Structural |
