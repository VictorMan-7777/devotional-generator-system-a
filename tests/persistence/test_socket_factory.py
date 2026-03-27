from __future__ import annotations

from pathlib import Path

import pytest

from src.models.registry import ScriptureRecord
from src.persistence.adapters.sqlite_adapter import SQLiteRegistrySocket
from src.persistence.reliable_socket import ReliableDatabaseSocket
from src.persistence.config import PersistenceConfig, PersistenceConfigError
from src.persistence.factory import create_socket


class TestSocketFactory:
    def test_create_sqlite_socket(self, tmp_path: Path) -> None:
        cfg = PersistenceConfig(default_provider="sqlite", sqlite_path=tmp_path / "r.db")
        socket = create_socket(cfg, component="registry")
        assert isinstance(socket, ReliableDatabaseSocket)
        assert isinstance(socket.inner, SQLiteRegistrySocket)

    def test_reject_legacy_json_as_runtime_provider(self) -> None:
        cfg = PersistenceConfig(default_provider="legacy_json", sqlite_path=Path("ignored.db"))
        with pytest.raises(PersistenceConfigError, match="source-only"):
            create_socket(cfg, component="registry")

    def test_reject_unknown_provider(self) -> None:
        cfg = PersistenceConfig(default_provider="postgres", sqlite_path=Path("ignored.db"))
        with pytest.raises(PersistenceConfigError, match="Unsupported provider"):
            create_socket(cfg, component="registry")

    def test_component_override_provider(self, tmp_path: Path) -> None:
        cfg = PersistenceConfig(
            default_provider="postgres",
            sqlite_path=tmp_path / "r.db",
            component_providers={"registry": "sqlite"},
        )
        socket = create_socket(cfg, component="registry")
        assert isinstance(socket, ReliableDatabaseSocket)
        assert isinstance(socket.inner, SQLiteRegistrySocket)

    def test_socket_record_scripture_use_returns_record(self, tmp_path: Path) -> None:
        cfg = PersistenceConfig(default_provider="sqlite", sqlite_path=tmp_path / "r.db")
        socket = create_socket(cfg, component="registry")
        socket.create_series("s1")
        socket.create_volume("v1", "s1", 1)
        rec = socket.record_scripture_use("v1", "Romans 8:15", "NIV")
        assert isinstance(rec, ScriptureRecord)

    def test_socket_logs_autoresearch_experiment(self, tmp_path: Path) -> None:
        cfg = PersistenceConfig(default_provider="sqlite", sqlite_path=tmp_path / "r.db")
        socket = create_socket(cfg, component="registry")
        rec = socket.log_autoresearch_experiment(
            experiment_id="exp-001",
            worker_name="outliner",
            benchmark_name="sinai-boundary",
            benchmark_reference="Exodus 19-20",
            run_slug="run-001",
            status="keep",
            attempted_change="Refine day boundaries",
            metrics_json="{}",
            learning_note="Better week turn",
            keep_decision="keep",
            created_at_utc="2026-03-14T01:00:00Z",
            completed_at_utc="2026-03-14T01:05:00Z",
        )
        assert rec.worker_name == "outliner"
        rows = socket.list_autoresearch_experiments(worker_name="outliner")
        assert len(rows) == 1
        assert rows[0].benchmark_name == "sinai-boundary"


class TestPersistenceConfig:
    def test_from_env_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEVG_DB_PROVIDER", raising=False)
        monkeypatch.delenv("DEVG_SQLITE_PATH", raising=False)
        monkeypatch.delenv("DEVG_DB_PROVIDER_REGISTRY", raising=False)
        cfg = PersistenceConfig.from_env()
        assert cfg.default_provider == "sqlite"
        assert cfg.sqlite_path == Path("registry.db")
        assert cfg.component_providers == {}

    def test_from_env_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEVG_DB_PROVIDER", "sqlite")
        monkeypatch.setenv("DEVG_SQLITE_PATH", "/tmp/devg-registry.db")
        monkeypatch.setenv("DEVG_DB_PROVIDER_REGISTRY", "sqlite")
        cfg = PersistenceConfig.from_env()
        assert cfg.default_provider == "sqlite"
        assert cfg.sqlite_path == Path("/tmp/devg-registry.db")
        assert cfg.provider_for("registry") == "sqlite"
