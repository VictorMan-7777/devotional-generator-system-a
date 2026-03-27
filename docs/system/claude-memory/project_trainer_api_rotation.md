---
name: Trainer API rotation and switching policy
description: Workers are spread across codex/claude/grok by default. Switching a trainer API is a deliberate intervention tool, not a routine change.
type: project
---

Workers are distributed across three LLM APIs by default (see `src/llm/router.py`):
- **Codex (GPT-4o):** outliner, action_writer, library_trainer
- **Claude (Anthropic):** prayer_writer, quote_selector, theological_reviewer, policy_guardian
- **Grok (xAI):** exposition_writer, be_still_writer, research_librarian, grammar_advisor

The rotation is intact — no global override is set in .env.local.

**Trainer switching:** When a worker is flat/declining for 100+ experiments and the training loop is sound, the trainer API itself may be the bottleneck. Switching (e.g., outliner from codex → claude) is a valid intervention. Grok proposes this via the normal proposal flow; Claude applies the per-worker env var change (e.g., `DEVG_LLM_OUTLINER=claude`).

**Rules:**
- One proposal at a time — Claude approves all switches before anything is applied
- Grok must provide clear reasoning: what he observed, what he ruled out, why a different LLM is a reasonable hypothesis. No fixed experiment thresholds — Grok evaluates the full picture.
- Balance decisions are Claude's call. Grok proposes; Claude judges nuance and timing.
- The xAI API (same API that powers Grok the daemon) is one of the three trainer options. Grok the daemon is the supervisor — he does not personally train workers.
