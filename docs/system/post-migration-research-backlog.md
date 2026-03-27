# Post-Migration Research Backlog

Items to examine after migration is stable and baseline fixes are confirmed.

## GitHub Repos for Autoresearch Pattern Adoption

**IMPORTANT**: Do NOT implement any of these until:
1. Migration is stable (clean boundary, no in-flight work, stable outputs)
2. Baseline outliner fixes are confirmed (pass rate improvement verified)
3. Frozen metrics are in place
4. Operator explicitly approves adoption

---

### 1. aiming-lab (GitHub org)
**URL**: https://github.com/aiming-lab
**Source**: ChatGPT suggestion

Patterns to evaluate:
- Multi-agent research coordination
- Iterative hypothesis testing frameworks
- Reward shaping for research agents

**Review questions**:
- Is there a pattern for injecting failure→remediation guidance into the next cycle?
- Does it handle deterministic workers differently from LLM workers?

---

### 2. ResearchClaw (ymx10086)
**URL**: https://github.com/ymx10086/ResearchClaw
**Source**: ChatGPT suggestion

Specific patterns identified during session (2026-03-20):

#### MetaClaw Skill Injection
- On stall detection: inject failure-category-specific guidance into the next proactive_assess prompt
- Different remedial text per failure category (e.g., "unanchored burden" gets different guidance than "adjacent duplicates")

#### Circuit Breaker (Validate-Before-Apply)
- Validate syntax + logical consistency before applying any code change
- Required guard: `py_compile.compile(path)` + import check before writing
- We already implemented the human-in-the-loop version of this (proposal flow)

#### Composite 8-Dimension Scoring
- Score experiments across 8 dimensions instead of a single score
- Would map well to our existing deterministic metrics (burden_unanchored, lane_unanchored, etc.)
- Each dimension gets its own trend line

#### Failure Categorization Ledger
- Track failure categories over time, not just scores
- When same category repeats 3+ times, escalate to code mutation
- Avoids the LLM trainer loop re-running same feedback forever

**Review questions**:
- Does the 8-dimension scoring require frozen metrics first? (Yes, almost certainly)
- Can failure categorization work with our current deterministic metrics?

---

### ChatGPT Cycle Guidance (2026-03-20)
From ChatGPT consultation on aggressive iteration:

- Each change must be attributable (one change per run, labelled)
- Detect → fix → retry immediately (tight loop)
- If failure signature unchanged after fix → fix didn't address root cause
- If failure signature changes → progress is being made, keep narrowing
- Stop condition for migration: clean boundary, no in-flight work, idle state confirmed

---

## When to Return to This File
- After outliner pass rate improves from current baseline
- After exposition_writer failure mode is diagnosed (1,567 experiments, 0 pass)
- After be_still/prayer/action writers are diagnosed (all 0% pass)
- After NAS migration is complete
