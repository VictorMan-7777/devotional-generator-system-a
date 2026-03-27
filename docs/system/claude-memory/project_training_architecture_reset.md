---
name: Training Architecture Reset (2026-03-19)
description: Training stopped. LLM-to-LLM loop identified as broken. Frozen metrics needed before restart. NAS migration in progress.
type: project
---

Training was stopped on 2026-03-19. A ChatGPT strategy session identified that the autoresearch loop has been in "insanity mode" — 620+ outliner experiments, 0 exposition passes, 94 be_still/action_writer experiments with 0 passes.

**Why:** No frozen evaluator. LLM trainers evaluate LLM or deterministic workers but scores drift and nothing in the deterministic workers ever changes. The loop measures without improving.

**The fix that must happen before restart:** Define frozen, deterministic metrics for each worker (what a Python function can score, not an LLM). See `docs/system/autoresearch-architecture-reset.md` for full analysis.

**Why:** Without a frozen metric, the loop is a proxy optimization — the workers get better at satisfying the LLM reviewer, not at producing better devotional content.

**Pending operator decision:** What is the frozen metric for Be Still, Action Steps, Exposition, and Outliner? The operator was thinking about this during NAS migration.

**Also pending:** Whether to use a local LLM (Ollama/Mistral) for generative workers instead of Anthropic/OpenAI, to eliminate API cost (~$25/week Anthropic vs ~$10/week OpenAI with no measurable improvement to show for it).

**How to apply:** Do NOT restart training until the frozen metrics discussion has happened. Ask the operator: "Have you decided on the frozen metrics?" before touching any training code.

**NAS migration:** Was in progress at time of writing. Verify DB path (`DEVG_DB_PATH`) is updated before running anything.
