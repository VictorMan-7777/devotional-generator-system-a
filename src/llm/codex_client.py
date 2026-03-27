"""codex_client.py — Concrete LLMClient implementation for OpenAI / Codex.

Reads OPENAI_API_KEY from environment.
Model is configurable via DEVG_CODEX_MODEL (default: gpt-4o).
Base URL configurable via DEVG_CODEX_BASE_URL for custom endpoints.
Max tokens via DEVG_CODEX_MAX_TOKENS (default: 2048).
"""
from __future__ import annotations

import os


class CodexLLMClient:
    """LLMClient implementation that calls OpenAI / Codex."""

    def __init__(
        self,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        try:
            import openai  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "openai package is required for CodexLLMClient. "
                "Install with: pip install openai"
            ) from exc

        self._model = model or os.environ.get("DEVG_CODEX_MODEL", "gpt-4o")
        self._max_tokens = max_tokens or int(os.environ.get("DEVG_CODEX_MAX_TOKENS", "2048"))
        self._client = openai.OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url or os.environ.get("DEVG_CODEX_BASE_URL") or None,
        )

    def generate(self, prompt: str, timeout: int = 300) -> str:
        """Send prompt to Codex/GPT and return the text response."""
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )
        return str(response.choices[0].message.content)
