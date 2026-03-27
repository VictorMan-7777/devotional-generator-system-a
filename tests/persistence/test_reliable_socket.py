from __future__ import annotations

from sqlalchemy.exc import OperationalError as SAOperationalError

from src.persistence.reliable_socket import ReliableDatabaseSocket


class _FakeSocket:
    def __init__(self) -> None:
        self.calls = 0

    def create_series(self, series_id: str, title: str | None = None) -> str:
        self.calls += 1
        if self.calls < 2:
            raise SAOperationalError("stmt", {}, Exception("database is locked"))
        return series_id

    def list_review_sections(self, run_slug: str):
        return [run_slug]


def test_reliable_socket_retries_transient_write_failure() -> None:
    fake = _FakeSocket()
    socket = ReliableDatabaseSocket(fake, retry_attempts=3, retry_delay_s=0.0)
    assert socket.create_series("s1") == "s1"
    assert fake.calls == 2


def test_reliable_socket_does_not_wrap_reads() -> None:
    fake = _FakeSocket()
    socket = ReliableDatabaseSocket(fake, retry_attempts=3, retry_delay_s=0.0)
    assert socket.list_review_sections("run-1") == ["run-1"]
