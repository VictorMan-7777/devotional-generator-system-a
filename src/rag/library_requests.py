from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.models.registry import ResourceAcquisitionRequestRecord
from src.persistence.config import PersistenceConfig
from src.persistence.factory import create_socket
from src.persistence.paths import default_registry_db_path


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_socket():
    cfg = PersistenceConfig.from_env()
    if cfg.sqlite_path == default_registry_db_path() and not cfg.sqlite_path.is_absolute():
        cfg = PersistenceConfig(
            default_provider=cfg.default_provider,
            sqlite_path=default_registry_db_path(),
            component_providers=cfg.component_providers,
        )
    return create_socket(cfg, component="registry")


def request_resource_acquisition(
    *,
    requested_by: str,
    scripture_reference: str,
    topic: str = "",
    worker_name: str = "",
    reason: str,
    requested_resource_kinds: list[str],
    status: str = "requested",
    notes: str = "",
    request_id: str | None = None,
) -> ResourceAcquisitionRequestRecord:
    socket = _build_socket()
    return socket.request_resource_acquisition(
        request_id=request_id or str(uuid.uuid4()),
        requested_by=requested_by,
        scripture_reference=scripture_reference,
        topic=topic,
        worker_name=worker_name,
        reason=reason,
        requested_resource_kinds=list(requested_resource_kinds or []),
        status=status,
        notes=notes,
        created_at_utc=_utc_now(),
        completed_at_utc="",
    )


def list_resource_acquisition_requests(
    *,
    requested_by: str | None = None,
    worker_name: str | None = None,
    scripture_reference: str | None = None,
    status: str | None = None,
) -> list[ResourceAcquisitionRequestRecord]:
    socket = _build_socket()
    return socket.list_resource_acquisition_requests(
        requested_by=requested_by,
        worker_name=worker_name,
        scripture_reference=scripture_reference,
        status=status,
    )


def update_resource_acquisition_request(
    *,
    request_id: str,
    status: str,
    notes: str,
    completed_at_utc: str | None = None,
) -> ResourceAcquisitionRequestRecord:
    socket = _build_socket()
    return socket.update_resource_acquisition_request(
        request_id=request_id,
        status=status,
        notes=notes,
        completed_at_utc=completed_at_utc or _utc_now(),
    )
