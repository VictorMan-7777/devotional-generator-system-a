"""Socket reliability wrapper: serialize writes and retry transient failures."""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy.exc import OperationalError as SAOperationalError

from src.persistence.socket import DatabaseSocket

_WRITE_METHODS = {
    "create_series",
    "create_volume",
    "record_quote_use",
    "record_scripture_use",
    "record_volume_day_plan",
    "record_volume_day_quote",
    "delete_volume",
    "seed_review_section",
    "save_review_edit",
    "save_review_decision",
    "log_autoresearch_experiment",
    "request_resource_acquisition",
    "update_resource_acquisition_request",
    "record_trainer_recommendation",
    "record_outliner_system_comparison",
}


class ReliableDatabaseSocket:
    """Serialize writes and retry transient persistence errors.

    This keeps generator/review code ignorant of backend locking behavior while
    still failing fast on non-transient exceptions.
    """

    def __init__(self, inner: DatabaseSocket, *, retry_attempts: int = 3, retry_delay_s: float = 0.2) -> None:
        self._inner = inner
        self._retry_attempts = max(1, retry_attempts)
        self._retry_delay_s = max(0.0, retry_delay_s)
        self._write_lock = threading.RLock()

    @property
    def inner(self) -> DatabaseSocket:
        return self._inner

    def __getattr__(self, name: str) -> Any:
        target = getattr(self._inner, name)
        if not callable(target):
            return target
        if name not in _WRITE_METHODS:
            return target

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            with self._write_lock:
                return self._run_with_retry(target, *args, **kwargs)

        return wrapped

    def _run_with_retry(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        last_exc: Exception | None = None
        for attempt in range(1, self._retry_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:  # deliberate gate; only retry transient SQLite-ish failures
                if not _is_transient_write_error(exc) or attempt >= self._retry_attempts:
                    raise
                last_exc = exc
                time.sleep(self._retry_delay_s * attempt)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("socket retry loop exited without result")


def _is_transient_write_error(exc: Exception) -> bool:
    message = str(exc).lower()
    transient_tokens = (
        "database is locked",
        "database is busy",
        "disk i/o error",
        "unable to open database file",
    )
    if isinstance(exc, sqlite3.OperationalError):
        return any(token in message for token in transient_tokens)
    if isinstance(exc, SAOperationalError):
        return any(token in message for token in transient_tokens)
    cause = getattr(exc, "__cause__", None)
    if isinstance(cause, Exception):
        return _is_transient_write_error(cause)
    return False
