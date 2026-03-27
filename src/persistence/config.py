"""Persistence provider configuration for socket factory."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


class PersistenceConfigError(ValueError):
    """Invalid persistence configuration."""


@dataclass(frozen=True)
class PersistenceConfig:
    """Runtime persistence provider configuration.

    Supports global default provider plus per-component overrides so provider
    swaps can be partial (component-scoped) instead of all-or-nothing.
    """

    default_provider: str = "sqlite"
    sqlite_path: Path = Path("registry.db")
    component_providers: dict[str, str] = field(default_factory=dict)

    def provider_for(self, component: str) -> str:
        return self.component_providers.get(component, self.default_provider).strip().lower()

    @classmethod
    def from_env(cls) -> "PersistenceConfig":
        provider = os.getenv("DEVG_DB_PROVIDER", "sqlite").strip().lower()
        sqlite_path = Path(os.getenv("DEVG_SQLITE_PATH", "registry.db"))
        component_providers: dict[str, str] = {}
        for key, value in os.environ.items():
            if not key.startswith("DEVG_DB_PROVIDER_"):
                continue
            component = key.removeprefix("DEVG_DB_PROVIDER_").strip().lower()
            if component:
                component_providers[component] = value.strip().lower()
        return cls(
            default_provider=provider,
            sqlite_path=sqlite_path,
            component_providers=component_providers,
        )

    @classmethod
    def sqlite_memory(cls) -> "PersistenceConfig":
        # Keep historical test/runtime behavior in generation pipeline.
        return cls(default_provider="sqlite", sqlite_path=Path(":memory:"))
