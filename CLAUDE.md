# DevG — Devotional Generator System

A multi-agent AI system that produces daily devotional content (Be Still, Action Steps, Prayer, Exposition) grounded in scripture. The pipeline generates structured devotionals from scripture passages; the autoresearch system trains the AI workers that generate each section.

---

## Chain of Command

```
Operator → Claude (team lead) → Grok (supervisor) → Trainers & Workers
```

- **Operator** communicates with Claude only. Never communicate with operator through Grok.
- **Claude** reviews proposals, applies code changes, keeps Grok aligned with operator direction.
- **Grok** owns all operational training decisions — scheduling, assignments, revision logic, trainer feedback. Reports to Claude. Cannot apply code changes directly.
- **Trainers** evaluate worker output and produce scored feedback. LLM agents.
- **Workers** generate devotional content sections. Mostly deterministic; Outliner and Exposition use LLM.

---

## Hard Rules — Do Not Break Without Operator Decision

1. **Training is stopped.** Do not restart until frozen metrics are implemented (`src/autoresearch/frozen_metrics.py`) and operator confirms. See `docs/system/autoresearch-architecture-reset.md`.

2. **Grok designs, Claude applies.** When a worker fails or system needs redesign: post to Grok, apply his proposal. Claude does not independently design fixes except for obvious one-liners already diagnosed.

3. **No code changes without verification.** Only commit when fixes are confirmed by improved pass rates. Never commit speculatively.

4. **Structural changes require review before build.** New DB tables, new scripts, core infra changes — Grok proposes, Claude reviews, then builds. Grok does not apply these directly.

5. **Pipeline LLM constraint.** Only one LLM agent in the generation pipeline (serves RAG/Outliner/Research Librarian). Be Still, Action Steps, and Prayer MUST be deterministic. Do not wire `llm_prayer_generator.py` into the pipeline.

---

## Current System State (as of 2026-03-24)

**Training:** STOPPED. Three structural code bugs must be fixed first (be_still missing inward slot, prayer token-substitution defect, action output-type constraint). Grok is diagnosing; proposals pending.

**Supervisor:** The Python deterministic supervisor (`run_training_supervisor.py`) is stopped. Grok is building a replacement LLM-driven supervisor (`run_grok_supervisor.py`). Plan submitted; awaiting structural bug proposals before building.

**Grok watcher:** Running in tmux session `devg-watcher`. Watches `grok_workspace/` for changes to urgent.md, chat.md, proposals/, notifications/ — fires immediately on change.

**Frozen metrics:** Spec exists (`docs/system/frozen-metrics-spec.md`). 5 implementation clarifications resolved. Target: `src/autoresearch/frozen_metrics.py`. Not yet built.

**Competency graduation:** Operator-approved design (per-assignment-ID competency tracking replaces binary streak). Not yet implemented.

**Real pass rates (baseline 2026-03-21):** Exposition 0.5%, Outliner 8.4%, Be Still 3.0%, Prayer 6.7%, Action Steps 6.5%.

---

## Physical Architecture

- **Mac Studio** — runs Claude Code CLI, all long-running processes (training, Grok daemon, watcher)
- **MacBook** — hosts repo files, shared to Mac Studio via SMB at `/Volumes/claude-projects/projects/devotional-generator-system-a/`
- **Cloud APIs** — Grok/xAI (training supervisor), Anthropic (LLM trainers)
- **NAS** — not in use for DevG; migration planned post-competition

**Important:** SQLite WAL mode does not work reliably over SMB. Never run concurrent DB writes while supervisor is running.

---

## Key Databases

- **`registry.db`** (project root) — runtime DB used by supervisor. Authoritative for `autoresearch_experiments`, `resource_acquisition_requests`, all live tables.
- **`data/devg_registry.sqlite3`** — stale fork from manual indexing. Do not use for runtime. Merge pending after supervisor stops.
- Active DB path set by `DEVG_DB_PATH` in `.env.local` → points to `registry.db`.

---

## Grok Communication Channels

- **`grok_workspace/chat.md`** — passive, batch. Directives, Q&A, end-of-cycle pickup. Add `[Q]` lines; watcher fires `run_grok_chat.py` immediately on change.
- **`grok_workspace/urgent.md`** — active interrupt. `[GROK URGENT timestamp]` entries need immediate attention. Check `ACTIVE_ISSUE:` line — if set, a critical issue is in progress.
- **Proposals:** `grok_workspace/proposals/<name>.py` + `<name>.md`. Status logged to `grok_workspace/notifications/pending_approval.md`.

---

## What Grok Owns (No Approval Needed)

- Which workers run each cycle and in what order
- Assignment selection, passage assignment, revision decisions
- Trainer feedback and redirection
- Halting a worker or changing approach when stuck
- Cycle pacing and parallelism

## What Requires Claude Review Before Building

- New DB tables or schema changes
- New scripts or changes to core infrastructure
- Changes to how worker output is logged or measured
- Anything irreversible

---

## Proposal Lifecycle

`P (pending) → R (redo) or F (resolved)`

Grok writes `.py` + `.md` files to `grok_workspace/proposals/`, posts `PROPOSAL READY:` to `pending_approval.md`. Claude reviews, validates, applies if accepted, moves to `proposals/completed/`. See `grok_workspace/PROTOCOL.md` for full spec and `grok_workspace/PROPOSAL_TEMPLATE.md` for required fields.

---

## Key Files to Check for Current State

| What you need | Where to look |
|---|---|
| Training pass rates | `docs/system/outputs/*training-supervisor-cycle.json` (newest) |
| Outliner status | `docs/system/outputs/*outliner-training-cycle.json` (newest 3) |
| Pending proposals | `grok_workspace/notifications/pending_approval.md` |
| Grok directives/Q&A | `grok_workspace/chat.md` (tail) |
| Urgent issues | `grok_workspace/urgent.md` |
| Grok's memory | `grok_workspace/MEMORY.md` |
| Frozen metrics spec | `docs/system/frozen-metrics-spec.md` |
| Architecture reset context | `docs/system/autoresearch-architecture-reset.md` |
