"""id_policy.py — Phase 013 CP1 PrayerTraceMap ID generation policy.

Centralises PrayerTraceMap ID creation rules.

Contract:
- IDs are deterministic for identical prayer_id input.
- IDs are distinct for distinct prayer_id values (collision risk: negligible
  for expected catalog sizes with 8-hex-char SHA-256 prefix).
- IDs carry the prefix "ptm_" for human readability and type safety.
- No random UUID. No time dependency.
"""
from __future__ import annotations

import hashlib


def create_prayer_trace_map_id(prayer_id: str) -> str:
    """Return a deterministic PrayerTraceMap id for the given prayer_id.

    Format: ``"ptm_<8 hex chars>"`` where the 8 chars are the leading
    characters of the SHA-256 digest of prayer_id encoded as UTF-8.

    Args:
        prayer_id: The id of the PrayerSection being traced.

    Returns:
        A string of the form ``"ptm_xxxxxxxx"`` (12 chars total).

    Examples:
        >>> create_prayer_trace_map_id("prayer-001")
        'ptm_xxxxxxxx'  # stable, deterministic
    """
    digest = hashlib.sha256(prayer_id.encode("utf-8")).hexdigest()[:8]
    return f"ptm_{digest}"
