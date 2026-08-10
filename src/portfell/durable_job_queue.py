"""Durable job state-machine contracts shared by queue adapters."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

TERMINAL_JOB_STATUSES = frozenset({"succeeded", "partial", "failed", "cancelled"})
LEASE_DURATION = timedelta(minutes=5)


class JobQueueError(ValueError):
    """Raised for stable, non-secret durable queue state errors."""


@dataclass(frozen=True)
class DurableJob:
    """Payload-free durable queue projection."""

    job_id: str
    user_id: str
    project_id: str
    job_kind: str
    input_hash: str
    input_ref: str
    priority: int
    created_at: datetime
    status: str = "queued"
    attempt_count: int = 0
    available_at: datetime | None = None
    lease_owner: str | None = None
    lease_token: str | None = None
    lease_expires_at: datetime | None = None


@dataclass(frozen=True, order=True)
class OutboxEvent:
    """Payload-free durable lifecycle event identified by an immutable event id."""

    event_id: str
    user_id: str
    event_type: str
    aggregate_ref: str


class JobCursor(Protocol):
    """Minimal result boundary for durable job repository commands."""

    def fetchall(self) -> list[tuple[object, ...]]:
        """Return all affected rows."""

        ...


class JobConnection(Protocol):
    """Parameterized PostgreSQL command connection contract."""

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> JobCursor:
        """Execute a parameterized durable job command."""

        ...


class InMemoryDurableJobRepository:
    """Deterministic queue test double with compare-and-set lease ownership."""

    def __init__(self) -> None:
        self._jobs: dict[str, DurableJob] = {}
        self._job_ids_by_identity: dict[tuple[str, str], str] = {}

    def enqueue(self, job: DurableJob) -> DurableJob:
        """Create or return a job by its stable kind/input identity."""

        identity = (job.job_kind, job.input_hash)
        existing_id = self._job_ids_by_identity.get(identity)
        if existing_id is not None:
            return self._jobs[existing_id]
        if job.status != "queued":
            raise JobQueueError("job_initial_status_invalid")
        normalized = replace(job, available_at=job.available_at or job.created_at)
        self._jobs[job.job_id] = normalized
        self._job_ids_by_identity[identity] = job.job_id
        return normalized

    def claim(self, *, worker_id: str, now: datetime, limit: int) -> tuple[DurableJob, ...]:
        """Claim available or expired jobs using deterministic fairness order."""

        if limit < 1:
            raise JobQueueError("job_claim_limit_invalid")
        candidates = [job for job in self._jobs.values() if self._claimable(job, now)]
        claimed: list[DurableJob] = []
        ordered_jobs = sorted(
            candidates, key=lambda item: (-item.priority, item.created_at, item.job_id)
        )
        for job in ordered_jobs[:limit]:
            attempt_count = job.attempt_count + 1
            token = str(uuid5(NAMESPACE_URL, f"{job.job_id}:{attempt_count}:{worker_id}"))
            claimed_job = replace(
                job,
                status="running",
                attempt_count=attempt_count,
                lease_owner=worker_id,
                lease_token=token,
                lease_expires_at=now + LEASE_DURATION,
            )
            self._jobs[job.job_id] = claimed_job
            claimed.append(claimed_job)
        return tuple(claimed)

    def complete(self, *, job_id: str, lease_token: str | None, terminal_status: str) -> DurableJob:
        """Complete only the active lease holder's running job."""

        if terminal_status not in TERMINAL_JOB_STATUSES:
            raise JobQueueError("job_terminal_status_invalid")
        job = self._jobs.get(job_id)
        if job is None or job.status != "running" or job.lease_token != lease_token:
            raise JobQueueError("job_lease_not_owned")
        completed = replace(
            job,
            status=terminal_status,
            lease_owner=None,
            lease_token=None,
            lease_expires_at=None,
        )
        self._jobs[job_id] = completed
        return completed

    @staticmethod
    def _claimable(job: DurableJob, now: datetime) -> bool:
        available_at = job.available_at or job.created_at
        return (job.status == "queued" and available_at <= now) or (
            job.status == "running"
            and job.lease_expires_at is not None
            and job.lease_expires_at <= now
        )


class InMemoryOutboxRepository:
    """At-least-once delivery test double with event-id deduplication."""

    def __init__(self) -> None:
        self._events: dict[str, OutboxEvent] = {}
        self._delivered_ids: set[str] = set()

    def append(self, event: OutboxEvent) -> OutboxEvent:
        """Persist or return an event with the same immutable id."""

        existing = self._events.get(event.event_id)
        if existing is not None:
            if existing != event:
                raise JobQueueError("outbox_event_conflict")
            return existing
        self._events[event.event_id] = event
        return event

    def pending(self) -> tuple[OutboxEvent, ...]:
        """Return pending events in stable event-id order."""

        return tuple(
            event
            for event_id, event in sorted(self._events.items())
            if event_id not in self._delivered_ids
        )

    def mark_delivered(self, event_id: str) -> None:
        """Acknowledge an existing event idempotently."""

        if event_id not in self._events:
            raise JobQueueError("outbox_event_not_found")
        self._delivered_ids.add(event_id)


class PostgresDurableJobRepository:
    """PostgreSQL worker claim adapter using one bounded lock-skipping command."""

    def __init__(self, connection: JobConnection) -> None:
        self._connection = connection

    def claim_ids(self, *, worker_id: str, now: datetime, limit: int) -> tuple[str, ...]:
        """Claim ready work atomically and return only opaque job identifiers."""

        if limit < 1:
            raise JobQueueError("job_claim_limit_invalid")
        rows = self._connection.execute(
            """
with candidates as (
    select job_id
    from portfell_app.jobs
    where (status = 'queued' and available_at <= %s)
       or (status = 'running' and lease_expires_at <= %s)
    order by priority desc, created_at, job_id
    limit %s
    for update skip locked
)
update portfell_app.jobs as jobs
set status = 'running',
    attempt_count = jobs.attempt_count + 1,
    lease_owner = %s,
    lease_token = gen_random_uuid(),
    lease_expires_at = %s,
    heartbeat_at = %s,
    updated_at = %s
from candidates
where jobs.job_id = candidates.job_id
returning jobs.job_id::text
""",
            (now, now, limit, worker_id, now + LEASE_DURATION, now, now),
        ).fetchall()
        return tuple(_job_id(row) for row in rows)


def _job_id(row: tuple[object, ...]) -> str:
    value = row[0]
    if not isinstance(value, str) or not value:
        raise JobQueueError("job_claim_result_invalid")
    return value


def utc_now() -> datetime:
    """Expose an injectable UTC clock default for production adapters."""

    return datetime.now(UTC)
