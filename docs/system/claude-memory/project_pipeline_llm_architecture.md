---
name: Pipeline LLM Architecture
description: Only one LLM agent is permitted in the generation pipeline — a multi-worker agent serving RAG/exposition, Outliner, and Research Librarian. All other section generators are deterministic.
type: project
---

Original plan was zero LLMs in the pipeline (all deterministic). The Outliner was identified as needing to be an LLM agent. Decision was then made to have a single LLM agent serve multiple workers: RAG (exposition grounding), Outliner, and Research Librarian.

**Why:** Consolidating into one agent avoids multiple LLM calls proliferating through the pipeline. Multi-worker RAG agent coded 2026-03-17, still being verified before being written as a repo law.

**How to apply:**
- Be Still, Action Steps, and Prayer section generators MUST be deterministic — no LLM calls in the pipeline for these sections.
- `llm_prayer_generator.py` exists but is NOT wired into the live pipeline and violates this architecture — do not activate it.
- Do NOT create `llm_be_still_generator.py` or `llm_action_steps_generator.py` — these sections are deterministic.
- The TRAINERS for Be Still, Action Steps, and Prayer use LLM to EVALUATE deterministic output — that is correct and separate from the pipeline.
- The law governing this constraint is not yet ratified (pending verification of the multi-worker RAG agent). Do not treat it as unresolved — treat it as a known decision awaiting formal writing.
