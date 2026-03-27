"""router.py — LLMClient factory that routes to Claude, Codex, or Grok based on configuration.

Environment variables:
    DEVG_LLM_PROVIDER   — global default when no per-worker rotation applies ("claude" | "codex" | "grok")
    DEVG_LLM_FALLBACK   — "claude", "codex", or "grok"; used when primary is unavailable

Worker-specific overrides (optional — override the default rotation for a single worker):
    DEVG_LLM_OUTLINER               — override provider for the outliner worker
    DEVG_LLM_EXPOSITION_WRITER      — override provider for the exposition writer
    DEVG_LLM_QUOTE_SELECTOR         — override provider for the quote selector
    DEVG_LLM_THEOLOGICAL_REVIEWER   — override provider for the theological reviewer
    DEVG_LLM_GRAMMAR_ADVISOR        — override provider for the grammar advisor
    DEVG_LLM_LIBRARY_TRAINER        — override provider for the library trainer
    DEVG_LLM_BE_STILL_WRITER        — override provider for the be still writer
    DEVG_LLM_ACTION_WRITER          — override provider for the action writer
    DEVG_LLM_PRAYER_WRITER          — override provider for the prayer writer
    DEVG_LLM_RESEARCH_LIBRARIAN     — override provider for the research librarian
    DEVG_LLM_POLICY_GUARDIAN        — override provider for the policy guardian

Default rotation (active when no env var override and no DEVG_LLM_PROVIDER is set):
    outliner            → codex    (structured JSON / schema generation)
    exposition_writer   → grok     (diverse theological voice, fast-reasoning tier)
    quote_selector      → claude   (nuanced quote-to-passage fit judgment)
    be_still_writer     → grok     (contemplative prose, different voice)
    action_writer       → codex    (structured list generation)
    prayer_writer       → claude   (liturgical sensitivity)
    research_librarian  → grok     (synthesis + retrieval reasoning)
    theological_reviewer→ claude   (cross-evaluates codex + grok; deepest doctrinal reasoning)
    grammar_advisor     → grok     (fast + cheap prose review)
    library_trainer     → codex    (structured acquisition evaluation)
    policy_guardian     → claude   (compliance reading requires careful judgment)

DEVG_LLM_PROVIDER overrides the entire rotation when set.
Per-worker env vars override only that one worker.

Usage:
    from src.llm.router import get_llm_client

    client = get_llm_client(worker="outliner")
    result = client.generate(prompt)
"""
from __future__ import annotations

import os

from src.llm.interfaces import LLMClient

_VALID_PROVIDERS = {"claude", "codex", "grok"}

# Mapping of worker name to env var for per-worker provider overrides.
_WORKER_ENV_MAP: dict[str, str] = {
    # Content generators (active in training)
    "outliner": "DEVG_LLM_OUTLINER",
    "exposition_writer": "DEVG_LLM_EXPOSITION_WRITER",
    "quote_selector": "DEVG_LLM_QUOTE_SELECTOR",
    # Content generators (waiting — registered for future activation)
    "be_still_writer": "DEVG_LLM_BE_STILL_WRITER",
    "action_writer": "DEVG_LLM_ACTION_WRITER",
    "prayer_writer": "DEVG_LLM_PRAYER_WRITER",
    # RAG intelligence layer
    "research_librarian": "DEVG_LLM_RESEARCH_LIBRARIAN",
    # Evaluator/coaching agents
    "theological_reviewer": "DEVG_LLM_THEOLOGICAL_REVIEWER",
    "grammar_advisor": "DEVG_LLM_GRAMMAR_ADVISOR",
    "library_trainer": "DEVG_LLM_LIBRARY_TRAINER",
    # Compliance enforcement
    "policy_guardian": "DEVG_LLM_POLICY_GUARDIAN",
}

# Default provider per worker — active when no env var override is set and
# DEVG_LLM_PROVIDER is not explicitly configured. Spreads load across all
# three AI systems and ensures evaluators use a different AI than the workers
# they review wherever possible.
_DEFAULT_WORKER_ROTATION: dict[str, str] = {
    "outliner":             "codex",   # GPT-4o: strong on structured JSON/schema
    "exposition_writer":    "grok",    # grok-4.1-fast: fresh theological voice
    "quote_selector":       "claude",  # nuanced quote-to-passage fit judgment
    "be_still_writer":      "grok",    # contemplative prose, different voice
    "action_writer":        "codex",   # structured list generation
    "prayer_writer":        "claude",  # liturgical + poetic sensitivity
    "research_librarian":   "grok",    # synthesis + RAG reasoning
    "theological_reviewer": "claude",  # cross-evaluates codex + grok outputs
    "grammar_advisor":      "grok",    # fast + cheap prose review
    "library_trainer":      "codex",   # structured acquisition evaluation
    "policy_guardian":      "claude",  # compliance requires careful judgment
}


def _provider_for_worker(worker: str | None) -> str:
    """Return the resolved provider name for a given worker.

    Resolution order (highest → lowest priority):
      1. Per-worker env var (e.g. DEVG_LLM_OUTLINER=grok)
      2. Global DEVG_LLM_PROVIDER env var
      3. Default rotation table (_DEFAULT_WORKER_ROTATION)
      4. Hard fallback: "claude"
    """
    # 1. Per-worker env var override
    if worker and worker in _WORKER_ENV_MAP:
        env_key = _WORKER_ENV_MAP[worker]
        override = os.environ.get(env_key, "").strip().lower()
        if override in _VALID_PROVIDERS:
            return override

    # 2. Global provider override
    global_override = os.environ.get("DEVG_LLM_PROVIDER", "").strip().lower()
    if global_override in _VALID_PROVIDERS:
        return global_override

    # 3. Default rotation
    if worker and worker in _DEFAULT_WORKER_ROTATION:
        return _DEFAULT_WORKER_ROTATION[worker]

    # 4. Hard fallback
    return "claude"


def get_cross_llm_client(*, worker: str | None = None) -> LLMClient:
    """Return an LLMClient using a different provider from the primary worker.

    Used by cross-evaluators and independent reviewers that must use a different
    AI system than the agent whose work they are evaluating. Prevents the same
    model from both generating and validating its own output.

    Rotation:  claude → grok,  codex → claude,  grok → codex.
    Cycles through all three so no single AI is over-used for evaluation.
    """
    primary = _provider_for_worker(worker)
    _cross_map = {"claude": "grok", "codex": "claude", "grok": "codex"}
    cross = _cross_map.get(primary, "codex")

    if cross == "grok":
        from src.llm.grok_client import GrokLLMClient
        return GrokLLMClient()

    if cross == "codex":
        from src.llm.codex_client import CodexLLMClient
        return CodexLLMClient()

    from src.llm.claude_client import ClaudeLLMClient
    return ClaudeLLMClient()


def get_llm_client(*, worker: str | None = None) -> LLMClient:
    """Return an LLMClient for the specified worker.

    Args:
        worker: Optional worker name for per-worker provider routing.
                Examples: "outliner", "exposition_writer", "quote_selector".

    Returns:
        An LLMClient instance configured for the appropriate AI system.

    Raises:
        ValueError: If the configured provider is unrecognized.
        ImportError: If the required SDK is not installed.
    """
    provider = _provider_for_worker(worker)

    if provider == "claude":
        from src.llm.claude_client import ClaudeLLMClient
        return ClaudeLLMClient()

    if provider == "codex":
        from src.llm.codex_client import CodexLLMClient
        return CodexLLMClient()

    if provider == "grok":
        from src.llm.grok_client import GrokLLMClient
        return GrokLLMClient()

    raise ValueError(
        f"Unknown LLM provider: {provider!r}. "
        "Set DEVG_LLM_PROVIDER to 'claude', 'codex', or 'grok'."
    )
