from __future__ import annotations

import os
import shutil
from pathlib import Path


def default_registry_db_path() -> Path:
    env_value = str(os.getenv("DEVG_DB_PATH", "")).strip()
    if env_value:
        return Path(env_value)

    local_path = Path.home() / "Library" / "Application Support" / "DevG" / "devg_registry.sqlite3"
    legacy_path = Path(__file__).resolve().parents[2] / "data" / "devg_registry.sqlite3"

    local_path.parent.mkdir(parents=True, exist_ok=True)
    if not local_path.exists() and legacy_path.exists():
        shutil.copy2(str(legacy_path), str(local_path))
    return local_path
