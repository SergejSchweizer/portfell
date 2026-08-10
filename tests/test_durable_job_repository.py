from __future__ import annotations

from contextlib import nullcontext

import pytest

from portfell.durable_job_repository import (
    DurableJob,
    DurableJobError,
    OutboxEvent,
    PostgresDurableJobRepository,
)


class _Cursor:
    def __init__(
        self,
        row: tuple[object, ...] | None = None,
        rows: list[tuple[object, ...]] | None = None,
    ) -> None:
        self._row = row
        self._rows = rows or []

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class _Connection:
    def __init__(
        self,
        *,
        inserted: bool = True,
        rows: list[tuple[object, ...]] | None = None,
    ) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self._inserted = inserted
        self._rows = rows or []

    def transaction(self):
        return nullcontext()

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        if "returning job_id" in sql:
            return _Cursor(("job-1",) if self._inserted else None)
        if "for update skip locked" in sql:
            return _Cursor(rows=self._rows)
        return _Cursor()


def _job() -> DurableJob:
    return DurableJob("job-1", "user-1", "project-1", "quote_delta", "hash-1", "input-1")


def _event() -> OutboxEvent:
    return OutboxEvent("event-1", "user-1", "job_queued", "job-1")


def test_enqueue_inserts_outbox_only_for_new_logical_job() -> None:
    connection = _Connection()

    assert PostgresDurableJobRepository(connection).enqueue(job=_job(), event=_event()) == _job()

    statements = "\n".join(statement for statement, _ in connection.calls)
    assert "select set_config" in statements
    assert "on conflict (job_kind, input_hash) do nothing" in statements
    assert "insert into portfell_app.outbox_events" in statements


def test_enqueue_deduplicates_outbox_when_job_already_exists() -> None:
    connection = _Connection(inserted=False)

    PostgresDurableJobRepository(connection).enqueue(job=_job(), event=_event())

    assert all("outbox_events" not in statement for statement, _ in connection.calls)


def test_claim_uses_skip_locked_and_creates_one_attempt_per_claim() -> None:
    connection = _Connection(
        rows=[("job-1", "user-1", "project-1", "quote_delta", "hash-1", "input-1", 2)]
    )

    claimed = PostgresDurableJobRepository(connection).claim(worker_id="worker-1", batch_size=2)

    assert claimed[0].job_id == "job-1"
    assert claimed[0].lease_token
    statements = "\n".join(statement for statement, _ in connection.calls)
    assert "for update skip locked" in statements
    assert "insert into portfell_app.job_attempts" in statements


@pytest.mark.parametrize("worker_id, batch_size", [("", 1), ("worker-1", 0)])
def test_claim_rejects_invalid_worker_or_batch(worker_id: str, batch_size: int) -> None:
    with pytest.raises(DurableJobError, match="job_claim_invalid"):
        PostgresDurableJobRepository(_Connection()).claim(
            worker_id=worker_id, batch_size=batch_size
        )