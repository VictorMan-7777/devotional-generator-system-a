# DevG Proposal Template

**All proposals must follow this format. Submissions that skip required fields will be rejected without review.**

---

## Template

```
## Proposal: [short-slug]
**Type:** [code_fix | config_change | db_schema | trainer_switch | architectural]
**Target file(s):** [exact paths]
**Priority:** [critical | high | normal]

### Problem
[1-3 sentences. What is broken or missing? Be specific — name the function, line, or behavior.]

### Evidence
[Required. Experiment counts, score trends, error messages, or log excerpts.
For trainer_switch proposals: must include current experiment count (≥100) and score trend over last 20 runs.
"It seems like" or "probably" are not evidence.]

### Root Cause
[What is the underlying cause? Not the symptom — the mechanism.]

### Implementation
[The actual fix. For code: show the before/after diff or describe the exact change.
For config: show the exact key=value and which file it goes in.
For db_schema: show the CREATE TABLE or ALTER TABLE statement.
This section must be complete enough that Claude can apply it without guessing.]

### Verification
[How will we know it worked? Name the metric, experiment count, or observable behavior.
Example: "Pass rate on exposition_writer rises above 10% within 2 cycles."
Example: "parse_failed disappears from outliner experiment records."]

### Rollback
[How do we undo this if it makes things worse?]

### Gap Resolution Record
**Gap:** [What was broken — one sentence]
**Root Cause:** [Why it happened — mechanism, not symptom]
**Fix:** [What changed]
**Rule:** [What must always be true going forward]
**Validation:** [How we enforce it — test, assertion, or observable metric]
```

---

## Proposal Types and Special Requirements

### `trainer_switch`
Switching a worker's trainer API (grok → claude, claude → codex, etc.) requires:
- Experiment count ≥ 100 for that worker
- Score trend over last 20 runs (attach or summarize)
- Specific hypothesis for why a different trainer fixes the problem

### `db_schema`
New tables or column additions require:
- Full CREATE TABLE or ALTER TABLE statement
- Migration plan for existing rows (what happens to workers already in the DB)
- Update to any store.py functions that read/write the affected table

### `architectural`
Changes to graduation logic, training flow, or agent orchestration require:
- A clarifying_questions file submitted first (see below)
- Claude's written response before the full proposal is submitted

### `clarifying_questions` (pre-proposal)
For complex proposals (architectural, trainer_switch, db_schema), submit a questions file first:
```
File: grok_workspace/proposals/clarifying_questions_[topic].md
Format: numbered list of questions, one per line
```
Claude will respond in grok_workspace/notifications/ before the full proposal is expected.

---

## File Naming Convention

```
grok_workspace/proposals/[slug].py       # implementation (Python patch script or plain code)
grok_workspace/proposals/[slug].md       # proposal document (using this template)
```

Both files required. The `.py` file must be runnable Python (or clearly labeled as a config patch with instructions). A `.py` file containing only an env var line is not a valid implementation.

---

## Example: Valid Minimal Proposal

```
## Proposal: fix-library-trainer-status-field
**Type:** code_fix
**Target file(s):** src/autoresearch/library_trainer.py
**Priority:** high

### Problem
library_trainer omits the `status` field when logging experiments. This generates
~18 policy violations per supervisor cycle because the policy guardian expects
status ∈ {pass, fail, revise, completed}.

### Evidence
policy_guardian_report.json from last 3 cycles each flag 18 violations with
message: "missing status field — library_trainer". Confirmed by querying
autoresearch_experiments WHERE worker_name='library_trainer': status column is
NULL or empty string on all rows from the last 200 experiments.

### Root Cause
log_experiment() call in library_trainer.py line 142 does not pass the `status`
keyword argument. The function signature accepts it but it defaults to "".

### Implementation
In src/autoresearch/library_trainer.py, line 142, change:
    log_experiment(experiment_id=..., worker_name=..., benchmark_name=...)
to:
    log_experiment(experiment_id=..., worker_name=..., benchmark_name=..., status="completed")

### Verification
Zero policy violations for library_trainer in the next policy_guardian_report.json.

### Rollback
Revert the single-line change. No DB migration needed.

### Gap Resolution Record
**Gap:** library_trainer experiments missing status field, generating 18 policy violations/cycle
**Root Cause:** log_experiment() call site omitted the `status` keyword argument
**Fix:** Added `status="completed"` to log_experiment() call at line 142
**Rule:** Every log_experiment() call must pass an explicit status value
**Validation:** Zero policy violations for library_trainer in next policy_guardian_report.json
```
