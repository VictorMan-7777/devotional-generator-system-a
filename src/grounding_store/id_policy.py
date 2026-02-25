"""id_policy.py — Phase 007 CP1 GroundingMap ID generation policy.

Centralises GroundingMap ID creation rules.

Contract:
- IDs are deterministic for identical exposition_id input.
- IDs are distinct for distinct exposition_id values (collision risk: negligible
  for expected catalog sizes with 8-hex-char SHA-256 prefix).
- IDs carry the prefix "gm_" for human readability and type safety.
- No random UUID. No time dependency.
"""
from __future__ import annotations

import hashlib


def create_grounding_map_id(exposition_id: str) -> str:
    """Return a deterministic GroundingMap id for the given exposition_id.

    Format: ``"gm_<8 hex chars>"`` where the 8 chars are the leading
    characters of the SHA-256 digest of exposition_id encoded as UTF-8.

    Args:
        exposition_id: The id of the ExpositionSection being grounded.

    Returns:
        A string of the form ``"gm_xxxxxxxx"`` (12 chars total).

    Examples:
        >>> create_grounding_map_id("expo-001")
        'gm_xxxxxxxx'  # stable, deterministic
    """
    digest = hashlib.sha256(exposition_id.encode("utf-8")).hexdigest()[:8]
    return f"gm_{digest}"
