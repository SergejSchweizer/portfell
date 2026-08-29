from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from portfell.durable_job_queue import (
    DurableJob,
    InMemoryDurableJobRepository,
    InMemoryOutboxRepository,
    JobQueueError,
    OutboxEvent,
    PostgresDurableJobRepository,
    utc_now,
)


class _Cursor:
    def __init__(self, rows: list[tuple[object, ...]] | None = None) -> None:
        self._rows = rows or [("job-1",)]

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        return _Cursor()


def test_job_claim_order_is_priority_then_creation_time() -> None:
    repository = InMemoryDurableJobRepository()
    now = datetime(2026, 8, 10, tzinfo=UTC)
    repository.enqueue(_job("job-low", priority=0, created_at=now))
    repository.enqueue(_job("job-high", priority=1, created_at=now + timedelta(seconds=1)))

    claimed = repository.claim(worker_id="worker-a", now=now + timedelta(minutes=1), limit=2)

    assert [job.job_id for job in claimed] == ["job-high", "job-low"]
    assert all(job.status == "running" for job in claimed)


def test_stale_worker_cannot_complete_claim() -> None:
    repository = InMemoryDurableJobRepository()
    now = datetime(2026, 8, 10, tzinfo=UTC)
    repository.enqueue(_job("job-1", priority=0, created_at=now))
    first = repository.claim(worker_id="worker-a", now=now, limit=1)[0]
    second = repository.claim(worker_id="worker-b", now=now + timedelta(minutes=6), limit=1)[0]

    with pytest.raises(JobQueueError, match="job_lease_not_owned"):
        repository.complete(
            job_id="job-1", lease_token=first.lease_token, terminal_status="succeeded"
        )

    completed = repository.complete(
        job_id="job-1", lease_token=second.lease_token, terminal_status="succeeded"
    )
    assert completed.status == "succeeded"


def test_outbox_delivery_is_idempotent_by_event_id() -> None:
    repository = InMemoryOutboxRepository()
    event = OutboxEvent("event-1", "user-a", "job.queued", "job-1")

    assert repository.append(event) == event
    assert repository.append(event) == event
    assert repository.pending() == (event,)
    repository.mark_delivered("event-1")

    assert repository.pending() == ()


def test_postgres_claim_uses_skip_locked_and_bounded_parameters() -> None:
    connection = _Connection()
    now = datetime(2026, 8, 10, tzinfo=UTC)

    job_ids = PostgresDurableJobRepository(connection).claim_ids(
        worker_id="worker-a", now=now, limit=2
    )

    assert job_ids == ("job-1",)
    sql, parameters = connection.calls[0]
    assert "for update skip locked" in sql.lower()
    assert "limit %s" in sql.lower()
    assert parameters[2] == 2


def test_durable_queue_rejects_invalid_transitions_and_unknown_outbox_events() -> None:
    repository = InMemoryDurableJobRepository()
    now = datetime(2026, 8, 10, tzinfo=UTC)

    with pytest.raises(JobQueueError, match="job_initial_status_invalid"):
        repository.enqueue(
            replace(_job("job-invalid", priority=0, created_at=now), status="running")
        )
    with pytest.raises(JobQueueError, match="job_claim_limit_invalid"):
        repository.claim(worker_id="worker-a", now=now, limit=0)
    with pytest.raises(JobQueueError, match="job_terminal_status_invalid"):
        repository.complete(job_id="missing", lease_token=None, terminal_status="queued")
    outbox = InMemoryOutboxRepository()
    event = OutboxEvent("event-1", "user-a", "job.queued", "job-1")
    outbox.append(event)
    with pytest.raises(JobQueueError, match="outbox_event_conflict"):
        outbox.append(OutboxEvent("event-1", "user-a", "job.failed", "job-1"))
    with pytest.raises(JobQueueError, match="outbox_event_not_found"):
        outbox.mark_delivered("unknown")
    assert utc_now().tzinfo is UTC


def test_durable_queue_preserves_idempotency_and_defers_future_jobs() -> None:
    repository = InMemoryDurableJobRepository()
    now = datetime(2026, 8, 10, tzinfo=UTC)
    queued = _job("job-1", priority=0, created_at=now)
    normalized = repository.enqueue(queued)
    assert normalized.available_at == now
    assert repository.enqueue(replace(queued, job_id="job-duplicate")) == normalized
    future = replace(
        _job("job-2", priority=0, created_at=now), available_at=now + timedelta(minutes=1)
    )
    repository.enqueue(future)
    assert repository.claim(worker_id="worker-a", now=now, limit=2)[0].job_id == "job-1"
    with pytest.raises(JobQueueError, match="job_lease_not_owned"):
        repository.complete(job_id="missing", lease_token="missing", terminal_status="succeeded")


def test_postgres_claim_rejects_invalid_limit_and_job_id_projection() -> None:
    now = datetime(2026, 8, 10, tzinfo=UTC)
    with pytest.raises(JobQueueError, match="job_claim_limit_invalid"):
        PostgresDurableJobRepository(_Connection()).claim_ids(
            worker_id="worker-a", now=now, limit=0
        )

    class _InvalidConnection(_Connection):
        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
            self.calls.append((sql, parameters))
            return _Cursor([(None,)])

    with pytest.raises(JobQueueError, match="job_claim_result_invalid"):
        PostgresDurableJobRepository(_InvalidConnection()).claim_ids(
            worker_id="worker-a", now=now, limit=1
        )


def _job(job_id: str, *, priority: int, created_at: datetime) -> DurableJob:
    return DurableJob(
        job_id=job_id,
        user_id="user-a",
        project_id="project-1",
        job_kind="metadata",
        input_hash=f"input-{job_id}",
        input_ref=f"ref-{job_id}",
        priority=priority,
        created_at=created_at,
    )
