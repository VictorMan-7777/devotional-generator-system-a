# Session Handoff — 2026-03-18
**Purpose:** Brief a new Claude Code session to full situational awareness after a security update and reboot. Read this file first, then the referenced resources in order.

---

## 1. Project Identity

**Repo:** `/Volumes/claude-projects/projects/devotional-generator-system-a`
**Branch:** `feat/phase-014-rag-infrastructure`
**Main branch:** `main`
**Last commit:** `23be52e fix(rag): diversify ExpositionRAG result ordering via round-robin interleave`

This is a devotional book generator (DEVG) — a multi-agent AI pipeline that produces Reformed evangelical daily devotionals for KDP/PDF publishing. It is not a web app. The primary output is a multi-day devotional book.

---

## 2. Read These First (Persistent Context)

| File | What it contains |
|------|-----------------|
| `/Users/agentrunner/.claude/projects/-Volumes-claude-projects-projects-devotional-generator-system-a/memory/MEMORY.md` | Persistent memory index — feedback rules, project direction, architecture truth. **Read before doing anything.** |
| `docs/system/training-reference.md` | The authoritative record of every training worker: state, grading criteria, training gaps, history. Current for 2026-03-18. |
| `docs/system/outliner-integration-transfer.md` | Outliner architecture context — read before touching outliner code |
| `docs/system/outliner-trainer-agent-spec.md` | Outliner trainer design spec |

---

## 3. System Architecture (Quick Reference)

**Pipeline workers (one LLM agent each):**
- **Outliner** → `src/autoresearch/outliner_training_agent.py` + `src/autoresearch/llm_outliner_core.py`
- **Exposition Writer** → `src/generation/real_section_generator.py` (template) + `src/autoresearch/exposition_training_agent.py`
- **Research Librarian** → `src/rag/research_librarian.py`
- **RAG** → `src/rag/exposition.py` (ExpositionRAG, BM25-style SQLite catalog)

**Be Still / Action Steps / Prayer** are deterministic templates — no LLM yet.

**Training loop:** `scripts/autoresearch/run_training_loop.py` → spawns `run_training_supervisor.py` per cycle (blocking subprocess). Was running as PID 13515 before reboot.

**Database:** `data/devg_registry.sqlite3` — all experiments, excerpts, quotes, registry data.

---

## 4. Training State as of 2026-03-18

> Full details: `docs/system/training-reference.md` (per-worker sections)

### Experiment counts (from DB before shutdown)
| Worker | Total | Passes |
|--------|-------|--------|
| exposition_writer | 1,266 | 0 (LLM scoring only; template fixed — pending re-run) |
| outliner | 615 | 17 |
| passage_researcher | 557 | 536 |
| pdf_art_director | 146 | 107 |
| pdf_layout_engineer | 22 | 19 |
| research_librarian | 184 | — |

### Graduated workers
- **PDF Layout Engineer** ✅ graduated
- **Passage Researcher** ✅ effectively passing (536/557)
- **PDF Art Director** ✅ passing (107/146)

### Active bottleneck: Outliner (615 experiments, only 17 passes)

**Breakdown by benchmark:**
- `outline-only-6d_1w`: 393 experiments (bulk of the work)
- `outline-only-18d_3w`: 125 experiments — **current wall**
- `outline-only-12d_2w`: 70 experiments
- `outline-only-24d_4w`: 27 experiments

**Root cause of 18d wall:** Ruth 1 = 22 verses / 18 days = 1.22 verses/day. The LLM cannot reliably produce 18 distinct, passage-grounded outlines at this granularity. Score ceiling: 74/85.

**100-experiment governance gate:** BREACHED. The governance policy (see memory: `feedback_training_50_100_experiments.md`) requires a hard decision at 100 experiments. The outliner has run 615 without an operator decision on the ruth-1 18d wall. **This is the key unresolved governance issue.** The training loop does not enforce the gate in code — it continues indefinitely.

**Operator decision pending:** For ruth-1 18d, choose one:
1. Defer the template (skip 18d for ruth-1, continue with other passages/templates)
2. Accept the wall (18d graduation for ruth-1 comes later when the model improves)
3. The two new Ruth commentaries (see §6) may help — wait for re-run results first

---

## 5. What Was Done in This Session

### Bugs fixed
1. **`test_prepare_passage_resource_bundle_requests_acquisition_when_thin`** — `_escalate_if_thin()` in `src/rag/research_librarian.py` called `escalate_for_passage()` through a different module's import, bypassing the monkeypatch. Fixed: added a direct `request_resource_acquisition(status="trainer_review")` call in `_escalate_if_thin()`.

2. **`test_backup_file_is_readable_as_registry`** — `SeriesRegistry.backup()` used `shutil.copy2` which doesn't capture WAL-mode data. Fixed: replaced with sqlite3 online backup API (`src_conn.backup(dst_conn)`) in `src/registry/registry.py`.

**Test suite after fixes:** 0 failed, 457+ passing.

### Exposition writer template fixed
- `src/generation/real_section_generator.py` — `_build_exposition()` was generating 100% deterministic, scripture-free scaffolding. 1,212 training experiments produced zero improvement.
- **Fix:** Used `brief.focus_clause` as a direct verse quote in every paragraph. Fixed `_scripture_image()` to skip pericope headings (≤6 words) and find actual verse content.
- **Result:** Deterministic scorer went from 45–55 → **100/100** across all benchmarks.
- **Status:** LLM trainer verification pending (requires training loop to run an exposition cycle).

### Outliner trainer upgraded
- `src/autoresearch/llm_outliner_core.py` — `_TRAINER_REVIEW_PROMPT` and `build_llm_outliner_trainer_review()`
- Persona: generic "expert trainer" → **lifelong seminary professor and homiletician** with doctoral credentials
- New fields passed to prompt: `verse_count`, `verse_density` (verses/day)
- New rubric criterion 6: density < 1.5 verses/day is HIGH RISK; "too_thin" verdict hard-caps score at 84 (below 85 pass threshold)
- New output field: `theological_reviewer_consultation_needed` (bool) + `theological_reviewer_question`
- Helper: `_estimate_verse_count(artifact)` parses verse ranges from day brief scripture_references

### Ruth commentaries added to library
Two new commentaries acquired from archive.org and indexed (+1,772 rows in `excerpt_catalog`):

| Resource | Slug | Chunks | Ruth 1 retrieval |
|----------|------|--------|-----------------|
| Keil & Delitzsch: Joshua, Judges, Ruth | `keil-delitzsch-ruth` | 800 | 236 chunks |
| Pulpit Commentary Vol. 8: Judges and Ruth | `pulpit-commentary-ruth` | 972 | 379 chunks |

Both registered in:
- `data/library/resource-catalog.json` (catalog entries with `serves_needs: ["outline", "structure", "exposition"]`)
- `scripts/library/index_source_texts.py` (RESOURCES list, will re-index if rows drop below 10)

**Note on acquisition librarian bypass:** These were acquired manually (operator directive). The acquisition librarian agent was not exercised. Its ability to independently acquire resources is still unverified for new passages.

---

## 6. Open Issues / Pending Decisions

| # | Issue | Owner | Status |
|---|-------|-------|--------|
| 1 | **Outliner 100-gate governance breach** — 615 experiments, no decision on ruth-1 18d wall | Operator | ⚠️ Awaiting decision |
| 2 | **Exposition LLM trainer verification** — template fixed but LLM hasn't scored it yet | Training loop | ⏳ Automatic on next exposition cycle |
| 3 | **Cover designer not wired** — `src/cover/` module is complete (405 lines, 3 concepts, KDP-compliant) but not connected to pipeline or committed to git | Developer | Not started |
| 4 | **Acquisition librarian competence unverified** — has never been tested on a new passage independently | QA/training | Not started |
| 5 | **Trainer system prompt audit** — several trainer agents not yet updated to biblical scholar profile (memory: `feedback_trainer_biblical_scholar.md`) | Developer | Not started |
| 6 | **Training loop has no 100-gate enforcement in code** — governance rule exists in docs/memory, not enforced | Developer | Not started |
| 7 | **`/rc` (remote control) slash command** — user asked how to stop it; origin unknown, not found in plugin dirs | — | Unresolved |

---

## 7. Files Modified This Session (Not Yet Committed)

```
src/generation/real_section_generator.py     — exposition template fix + _scripture_image() fix
src/autoresearch/llm_outliner_core.py        — trainer persona upgrade + verse density rubric
src/rag/research_librarian.py                — _escalate_if_thin() direct request_resource_acquisition call
src/registry/registry.py                    — backup() sqlite3 online backup API
scripts/library/index_source_texts.py       — registered keil-delitzsch-ruth + pulpit-commentary-ruth
data/library/resource-catalog.json          — two new catalog entries
data/library/resources/keil-delitzsch-ruth/ — source.txt + holding.json (new)
data/library/resources/pulpit-commentary-ruth/ — source.txt + holding.json (new)
docs/system/training-reference.md           — annotated with 2026-03-18 findings
docs/system/session-handoff-2026-03-18.md   — this file
```

All changes are on branch `feat/phase-014-rag-infrastructure`. Nothing pushed to remote. No commits made this session.

---

## 8. How to Resume Training After Reboot

```bash
cd /Volumes/claude-projects/projects/devotional-generator-system-a
source .venv/bin/activate

# Verify test suite clean before starting
python -m pytest tests/ -x -q --ignore=tests/integration -m "not slow"

# Start training loop (was running at --interval-seconds 20)
nohup python scripts/autoresearch/run_training_loop.py --interval-seconds 20 \
  > logs/training-loop.log 2>&1 &
echo "Training loop PID: $!"
```

**Before restarting:** Confirm the operator decision on outliner ruth-1 18d (Issue #1 above). The loop will continue hammering it otherwise.

---

## 9. Key Code Locations

| Concern | File |
|---------|------|
| Exposition template | `src/generation/real_section_generator.py` — `_build_exposition()` |
| Outliner trainer prompt | `src/autoresearch/llm_outliner_core.py` — `_TRAINER_REVIEW_PROMPT` |
| Burden/lane generator prompt | `src/autoresearch/llm_outliner_core.py` — `_BURDEN_LANE_PROMPT` |
| Outliner training agent | `src/autoresearch/outliner_training_agent.py` |
| RAG retrieval | `src/rag/exposition.py` — `ExpositionRAG.retrieve_for_paragraph()` |
| Research librarian | `src/rag/research_librarian.py` — `prepare_passage_resource_bundle()` |
| Registry backup | `src/registry/registry.py` — `SeriesRegistry.backup()` |
| Library indexer | `scripts/library/index_source_texts.py` |
| Cover designer | `src/cover/engine.py` (untracked, not wired) |
| Training supervisor | `scripts/autoresearch/run_training_supervisor.py` |
