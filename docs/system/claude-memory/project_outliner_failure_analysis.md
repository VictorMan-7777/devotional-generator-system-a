---
name: Outliner failure analysis and fixes
description: Root cause analysis of outliner 2.5% pass rate, confirmed failure modes, and fixes applied
type: project
---

## Root cause: two bugs in reasoning_outliner_core.py

**Why:** 788 experiments, 2.5% pass rate, all failures deterministic. Two bugs confirmed by tracing actual failing passages.

### Bug 1: `key_terms()` treated capitalized divine pronouns as proper nouns

In poetic/psalmic texts (KJV/NASB), "His", "Him", "Nor", "But" are capitalized when referring to God. The proper-noun first pass (previously requiring 3+ chars) filled the 6-term limit with these useless 3-char words, crowding out actual distinctive terms like "despised", "abhorred", "affliction".

**Fix applied 2026-03-20**: Changed proper noun pass to require 4+ chars. Now finds actual names/places (Abraham, Isaac, Naomi, affliction) instead of divine pronouns.

### Bug 2: `_term_anchor()` used evaluator stopwords ("lord", "god") as anchors

The evaluator's `_meaningful_tokens()` excludes "lord" and "god" from its token set. If `_term_anchor` returned "lord" as the anchor, the generated lane/burden contained "lord" but the evaluator couldn't find it in the text — giving `lane_unanchored: True`.

**Fix applied 2026-03-20**: `_term_anchor` now filters `_EVALUATOR_STOPWORDS` (includes "lord", "god") from candidates. Also scans ALL terms (not just first 4) to find distinctive ones.

### Bug 3 (adjacent duplicate): Genre templates didn't include scripture_reference

Non-epistle templates were identical in structure; adjacent days with the same dominant key_term (e.g., "abraham" across Genesis 22:1-5 and 22:6-10) produced textually identical burdens/lanes → `adjacent_burden_duplicates` + `adjacent_lane_duplicates` each penalized -18/-20.

**Fix applied 2026-03-20**: All genre templates in `pastoral_burden()` and `theological_lane()` now embed the specific `reference` (e.g., "Genesis 22:1-5"), guaranteeing adjacent days with the same passage anchor still differ.

### Bug 4 (DB path): Supervisor used Library path DB (0 experiments) instead of registry.db

`default_registry_db_path()` returns `~/Library/Application Support/DevG/devg_registry.sqlite3` when `DEVG_DB_PATH` env var is unset. This file is 569MB but has 0 experiments. The outliner step's SQLAlchemy commit failed with `disk I/O error` against this DB (cycles 22-33, all rc=1 for outliner step).

**Fix applied 2026-03-20**: Added `DEVG_DB_PATH=/Volumes/claude-projects/projects/devotional-generator-system-a/registry.db` to both `.env` and `.env.local`. Supervisor's `_run_step()` loads `.env.local` fresh each call, so all subsequent cycles route to `registry.db` (4,569 experiments).

### Files modified
- `src/autoresearch/reasoning_outliner_core.py` — bugs 1, 2, 3
- `.env` — bug 4 (DEVG_DB_PATH for direct runs)
- `.env.local` — bug 4 (DEVG_DB_PATH for supervisor subprocesses)

### Also restored (corrupted by Grok)
- `src/autoresearch/reasoning_outliner_core.py` — had `[boot original full]` on line 1
- `src/autoresearch/llm_outliner_core.py` — had garbage patch text as module docstring (unterminated triple-quote)
Both restored via `git checkout <hash> -- <file>`.

### Bible version: NASB (not KJV)
Training uses NASB throughout. Bolls.life primary (NASB default), API.Bible fallback (NASB 1995, operator-supplied key). All 4,569 experiments scored against NASB text. No version mismatch between training and production.

## Failure modes (quantified)
- `burden_unanchored` + `lane_unanchored` > 0: affects longer devotionals (18d+), now fixed
- `adjacent_burden_duplicates` + `adjacent_lane_duplicates`: when adjacent days have similar text
- `application_unanchored`: application lane contained non-passage words, fixed by key_terms fix
- `broad_key_verse_references: 6`: all days have broad refs — historical issue from old code version

## Experiment store location
- Real store: `registry.db` at project root (NOT `data/devg_registry.sqlite3`)
- 4,515 total experiments as of 2026-03-20
- Outliner: 788 exp (20 pass 2.5%, 601 fail, 146 revise)
- Exposition: 1,567 exp (0 pass, 484 fail) — unknown failure mode
- Passage researcher/PDF workers: graduated

## How to apply:
Apply fixes before running training cycles. After fixes, re-run outliner benchmarks to confirm improvement. Target: deterministic_score ≥ 85 on all benchmarks.
