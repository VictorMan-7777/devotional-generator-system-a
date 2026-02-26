"""interfaces.py — Phase 012 LLM client protocol.

Defines the injectable LLMClient interface used by LLMExpositionGenerator.
No concrete network implementation is provided here.

Contract:
- Single method: generate(prompt) -> str
- No network calls in this module.
- No LLM framework imports.
"""
from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """Structural protocol for injectable LLM clients.

    Any object implementing ``generate(prompt: str) -> str`` satisfies
    this protocol — no explicit inheritance required.
    """

    def generate(self, prompt: str) -> str:
        """Send a prompt to the LLM and return the generated text.

        Args:
            prompt: The full prompt string to send.

        Returns:
            The generated text string.
        """
        ...
