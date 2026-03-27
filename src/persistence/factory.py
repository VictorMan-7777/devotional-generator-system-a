"""Persistence socket factory."""

from __future__ import annotations

from src.persistence.adapters.sqlite_adapter import SQLiteRegistrySocket
from src.persistence.config import PersistenceConfig, PersistenceConfigError
from src.persistence.reliable_socket import ReliableDatabaseSocket
from src.persistence.socket import DatabaseSocket


def create_socket(config: PersistenceConfig, component: str = "registry") -> DatabaseSocket:
    """Create a persistence socket from provider config.

    Runtime support in this phase is SQLite only. Other providers are planned and
    intentionally rejected with a clear error to prevent accidental partial usage.
    """

    provider = config.provider_for(component)
    if provider == "sqlite":
        return ReliableDatabaseSocket(SQLiteRegistrySocket(db_path=config.sqlite_path))
    if provider == "legacy_json":
        raise PersistenceConfigError(
            f"legacy_json is source-only and cannot be selected as active runtime provider "
            f"(component={component})."
        )
    raise PersistenceConfigError(
        f"Unsupported provider '{provider}' for component '{component}'. "
        f"Supported runtime provider(s) currently implemented: sqlite."
    )
