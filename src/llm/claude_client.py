"""claude_client.py — Concrete LLMClient implementation for Anthropic Claude.

Reads ANTHROPIC_API_KEY from environment.
Model is configurable via DEVG_CLAUDE_MODEL (default: claude-sonnet-4-6).
Max tokens via DEVG_CLAUDE_MAX_TOKENS (default: 2048).

Automatic fallback: on Anthropic 529 OverloadedError, retries once via CodexLLMClient
(OpenAI) if OPENAI_API_KEY is available. Keeps Anthropic as primary; OpenAI absorbs
overload bursts without manual intervention.
"""
from __future__ import annotations

import os


class ClaudeLLMClient:
    """LLMClient implementation that calls Anthropic Claude.

    Falls back to OpenAI automatically on 529 OverloadedError if OPENAI_API_KEY is set.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        api_key: str | None = None,
    ) -> None:
        import anthropic  # type: ignore[import]

        self._model = model or os.environ.get("DEVG_CLAUDE_MODEL", "claude-sonnet-4-6")
        self._max_tokens = max_tokens or int(os.environ.get("DEVG_CLAUDE_MAX_TOKENS", "2048"))
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
        )

    def generate(self, prompt: str, timeout: int = 300) -> str:
        """Send prompt to Claude and return the text response.

        On Anthropic 529 OverloadedError, falls back to OpenAI if OPENAI_API_KEY is set.
        """
        import anthropic  # type: ignore[import]
        import anthropic._exceptions as _anthropic_exc  # type: ignore[import]
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )
            return str(message.content[0].text)
        except (_anthropic_exc.OverloadedError, _anthropic_exc.RateLimitError):
            openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
            if not openai_key:
                raise
            from src.llm.codex_client import CodexLLMClient
            fallback = CodexLLMClient(max_tokens=self._max_tokens)
            return fallback.generate(prompt, timeout=timeout)
        except _anthropic_exc.BadRequestError as exc:
            # Credit balance exhausted returns a 400 BadRequestError.
            # Fall back to OpenAI rather than silently swallowing the error.
            if "credit balance" in str(exc).lower() or "billing" in str(exc).lower():
                openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
                if openai_key:
                    from src.llm.codex_client import CodexLLMClient
                    fallback = CodexLLMClient(max_tokens=self._max_tokens)
                    return fallback.generate(prompt, timeout=timeout)
            raise
