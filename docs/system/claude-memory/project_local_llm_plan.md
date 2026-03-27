---
name: Local LLM Architecture Plan
description: Replace Anthropic/OpenAI with Ollama on Mac Studio. MacBook runs code, NAS holds data. Setup steps documented.
type: project
---

Replace API-based LLM calls with a local Ollama instance on Mac Studio to eliminate ~$35/week API costs with no measurable training improvement.

**Split:** MacBook runs training loop + workers. Mac Studio runs Ollama (LLM server) + DevG socket server. NAS holds all data.

**Why socket server on Studio:** SQLite over SMB under frequent writes causes disk I/O errors (already observed). Studio has the fastest NAS connection; socket server there serializes all DB writes without SMB contention.

**Model recommendation:** Start with `mistral` or `llama3.1:8b` (4–5GB RAM). Only upgrade to 70B if smaller model demonstrably fails once frozen metrics are in place.

**Key env vars needed on MacBook:**
- `DEVG_LLM_BASE_URL=http://mac-studio.local:11434`
- `DEVG_LLM_PROVIDER=ollama`
- `DEVG_DB_PATH` updated to NAS path

**New code needed:** `src/llm/ollama_client.py` implementing the same `generate(prompt) -> str` interface. Register in router.py. Everything else unchanged.

**How to apply:** After NAS migration, before writing any code, read `docs/system/local-llm-architecture-plan.md` for full setup steps and `docs/system/autoresearch-architecture-reset.md` for context on why training was stopped.

**Critical:** Local LLM does NOT fix the insanity loop on its own. Frozen metrics must be defined first. See training architecture reset doc.
