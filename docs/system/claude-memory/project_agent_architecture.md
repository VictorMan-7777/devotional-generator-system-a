---
name: Agent Architecture Truth
description: All training workers are deterministic Python — no LLM calls exist. LLM infrastructure added 2026-03-16. Key decisions about what "agent" means in this system.
type: project
---

Every worker labeled "agent" (outliner, exposition_writer, theological_reviewer, etc.) was deterministic Python — no Claude or Codex calls. User expected AI agent calls. Infrastructure added 2026-03-16.

**Why:** "Any position called an agent is expected to be an AI Agent." Workers should call Claude/Codex, not run Python templates.

**What was added:**
- `src/llm/interfaces.py` — LLMClient protocol (existed)
- `src/llm/claude_client.py` — Anthropic SDK client (new)
- `src/llm/codex_client.py` — OpenAI SDK client (new, requires pip install openai)
- `src/llm/router.py` — Routes to Claude or Codex via DEVG_LLM_PROVIDER env var
- `src/autoresearch/llm_outliner_core.py` — LLM-backed outliner using actual AI calls
- `anthropic>=0.84` added to pyproject.toml dependencies

**Configuration:**
- `DEVG_LLM_PROVIDER=claude` (default) or `codex`
- `ANTHROPIC_API_KEY` — required for Claude
- `OPENAI_API_KEY` — required for Codex
- `DEVG_OUTLINER_MODE=llm` (default), `reasoning` (deterministic fallback), `legacy`

**How to apply:** When any worker shows all-fail training data with no signal, check if it's running a Python template vs actual AI. Use `src/llm/router.get_llm_client(worker=...)` to add AI calls.
