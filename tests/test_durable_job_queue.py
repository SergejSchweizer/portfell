from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from portfell.durable_job_queue import (
    DurableJob,
    InMemoryDurableJobRepository,
    InMemoryOutboxRepository,
    JobQueueError,
    OutboxEvent,
    PostgresDurableJobRepository,
)


class _Cursor:
    def fetchall(self) -> list[tuple[object, ...]]:
        return [("job-1",)]


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
