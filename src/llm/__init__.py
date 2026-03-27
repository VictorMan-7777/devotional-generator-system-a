"""LLM client infrastructure for DevG.

Provides injectable, configurable AI agent calls to Claude, Codex, and Grok.
Workers use get_llm_client(worker=...) from src.llm.router to get the
appropriate client based on DEVG_LLM_PROVIDER environment configuration.

Environment variables:
    DEVG_LLM_PROVIDER            — "claude" (default), "codex", or "grok"
    ANTHROPIC_API_KEY            — required for Claude
    OPENAI_API_KEY               — required for Codex
    XAI_API_KEY                  — required for Grok (xAI API)
    DEVG_CLAUDE_MODEL            — Claude model override (default: claude-sonnet-4-6)
    DEVG_CODEX_MODEL             — Codex model override (default: gpt-4o)
    DEVG_GROK_MODEL              — Grok model override (default: grok-4.1-fast-reasoning)
    DEVG_GROK_MAX_TOKENS         — Grok max tokens override (default: 2048)

Per-worker overrides (optional, override DEVG_LLM_PROVIDER for a specific worker):
    DEVG_LLM_OUTLINER            — outliner (generates editorial outlines)
    DEVG_LLM_EXPOSITION_WRITER   — exposition writer (generates devotional exposition text)
    DEVG_LLM_THEOLOGICAL_REVIEWER — theological reviewer (reviews content for doctrinal accuracy)
    DEVG_LLM_GRAMMAR_ADVISOR     — grammar advisor (reviews prose quality)
    DEVG_LLM_LIBRARY_TRAINER     — library trainer (reviews library acquisition quality)
    DEVG_LLM_RESEARCH_LIBRARIAN  — research librarian (seminary intelligence layer over RAG)
    DEVG_LLM_POLICY_GUARDIAN     — policy guardian (reads agent artifacts against written law)
    DEVG_LLM_QUOTE_SELECTOR      — quote selector (selects appropriate quotes)
    DEVG_LLM_BE_STILL_WRITER     — be still writer
    DEVG_LLM_ACTION_WRITER       — action steps writer
    DEVG_LLM_PRAYER_WRITER       — prayer writer

Grok model reference (as of 2026-03-19, $in / $out per 1M tokens):
    grok-4.20-0309-reasoning     $2.00 / $6.00 — reasoning-heavy analysis & coding
    grok-4.20-0309-non-reasoning $2.00 / $6.00 — structured generation, no CoT
    grok-4-1-fast-reasoning      $0.20 / $0.50 — default; good for most tasks
    grok-4-1-fast-non-reasoning  $0.20 / $0.50 — fastest, no chain-of-thought
    grok-4.20-multi-agent-0309   $2.00 / $6.00 — requires Responses API (not chat completions)
"""
