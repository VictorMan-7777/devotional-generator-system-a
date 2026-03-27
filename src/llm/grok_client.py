"""grok_client.py — Concrete LLMClient implementation for xAI Grok.

xAI's API is OpenAI-compatible, so this reuses the openai SDK with a
different base URL and API key.

Environment variables:
    XAI_API_KEY             — required
    DEVG_GROK_MODEL         — model override (default: grok-4-1-fast-reasoning)
    DEVG_GROK_MAX_TOKENS    — max tokens override (default: 2048)

Model reference (as of 2026-03-19, $in / $out per 1M tokens):
    grok-4.20-0309-reasoning      $2.00 / $6.00 — reasoning-heavy analysis & coding
    grok-4.20-0309-non-reasoning  $2.00 / $6.00 — structured generation, no CoT
    grok-4-1-fast-reasoning       $0.20 / $0.50 — default; good for most tasks
    grok-4-1-fast-non-reasoning   $0.20 / $0.50 — fastest, no chain-of-thought

Note: grok-4.20-multi-agent-0309 requires the Responses API, not chat completions.
      Use grok-4.20-0309-reasoning for complex analysis via this client.
"""
from __future__ import annotations

import os
from pathlib import Path

_XAI_BASE_URL = "https://api.x.ai/v1"
_DOTENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def _load_dotenv() -> None:
    """Load .env from project root if present, without requiring python-dotenv."""
    if not _DOTENV_PATH.exists():
        return
    with _DOTENV_PATH.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Only set if not already present — shell exports always win
            if key and key not in os.environ and value:
                os.environ[key] = value


class GrokLLMClient:
    """LLMClient implementation that calls xAI Grok via OpenAI-compatible API."""

    def __init__(
        self,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        api_key: str | None = None,
    ) -> None:
        _load_dotenv()
        try:
            import openai  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "openai package is required for GrokLLMClient. "
                "Install with: pip install openai"
            ) from exc

        self._model = model or os.environ.get("DEVG_GROK_MODEL", "grok-4-1-fast-reasoning")
        self._max_tokens = max_tokens or int(os.environ.get("DEVG_GROK_MAX_TOKENS", "2048"))
        self._client = openai.OpenAI(
            api_key=api_key or os.environ.get("XAI_API_KEY"),
            base_url=_XAI_BASE_URL,
        )

    def generate(self, prompt: str, timeout: int = 300) -> str:
        """Send prompt to Grok and return the text response."""
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )
        return str(response.choices[0].message.content)
