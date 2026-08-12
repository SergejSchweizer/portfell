"""PostgreSQL repository for durable job enqueueing and worker claims."""

from __future__ import annotations

import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from portfell.hosted_catalog import set_authenticated_user_sql


class DurableJobError(ValueError):
    """Raised when a durable job command violates its state contract."""


@dataclass(frozen=True)
class DurableJob:
    """Payload-free durable job control-plane record."""

    job_id: str
    user_id: str
    project_id: str
    job_kind: str
    input_hash: str
    input_ref: str
    priority: int = 0


@dataclass(frozen=True)
class OutboxEvent:
    """Deduplicable event emitted only with a newly queued job."""

    event_id: str
    user_id: str
    event_type: str
    aggregate_ref: str


@dataclass(frozen=True)
class ClaimedJob:
    """A job lease owned by one worker until its expiry."""

    job_id: str
    user_id: str
    project_id: str
    job_kind: str
    input_hash: str
    input_ref: str
    priority: int
    lease_token: str


class DurableJobCursor(Protocol):
    """Minimal PostgreSQL result boundary for queue commands."""

    def fetchone(self) -> tuple[object, ...] | None: ...

    def fetchall(self) -> list[tuple[object, ...]]: ...


class DurableJobConnection(Protocol):
    """Transactional parameterized boundary for queue commands."""

    def transaction(self) -> AbstractContextManager[object]: ...

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> DurableJobCursor: ...


class PostgresDurableJobRepository:
    """Atomically queue jobs and claim bounded worker batches."""

    def __init__(self, connection: DurableJobConnection) -> None:
        self._connection = connection

    def enqueue(self, *, job: DurableJob, event: OutboxEvent) -> DurableJob:
        """Insert one logical job and its outbox event in one transaction."""

        if event.user_id != job.user_id or event.aggregate_ref != job.job_id:
            raise DurableJobError("job_outbox_identity_invalid")
        with self._connection.transaction():
            self._connection.execute(*set_authenticated_user_sql(job.user_id))
            inserted = self._connection.execute(
                """
insert into portfell_app.jobs (
    job_id, user_id, project_id, job_kind, input_hash, input_ref, status, priority
) values (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, 'queued', %s)
on conflict (job_kind, input_hash) do nothing
returning job_id
""",
                (
                    job.job_id,
                    job.user_id,
                    job.project_id,
                    job.job_kind,
                    job.input_hash,
                    job.input_ref,
                    job.priority,
                ),
            ).fetchone()
            if inserted is None:
                return job
            self._connection.execute(
                """
insert into portfell_app.outbox_events (event_id, user_id, event_type, aggregate_ref)
values (%s::uuid, %s::uuid, %s, %s)
on conflict (event_id) do nothing
""",
                (event.event_id, event.user_id, event.event_type, event.aggregate_ref),
            )
        return job

    def claim(self, *, worker_id: str, batch_size: int) -> tuple[ClaimedJob, ...]:
        """Claim an available bounded batch without blocking competing workers."""

        if not worker_id or batch_size < 1:
            raise DurableJobError("job_claim_invalid")
        lease_token = str(uuid.uuid4())
        with self._connection.transaction():
            rows = self._connection.execute(
                """
with claimable as (
    select job_id
    from portfell_app.jobs
    where status = 'queued' and available_at <= now()
    order by priority desc, created_at, job_id
    limit %s
    for update skip locked
)
update portfell_app.jobs as job
set status = 'running', lease_owner = %s, lease_token = %s::uuid,
    lease_expires_at = now() + interval '5 minutes', heartbeat_at = now(),
    attempt_count = job.attempt_count + 1, updated_at = now()
from claimable
where job.job_id = claimable.job_id
returning job.job_id::text, job.user_id::text, job.project_id::text, job.job_kind,
          job.input_hash, job.input_ref, job.priority
""",
                (batch_size, worker_id, lease_token),
            ).fetchall()
            for row in rows:
                claimed = _claimed_job(row, lease_token)
                self._sync_initial_fill_status(
                    job_id=claimed.job_id,
                    user_id=claimed.user_id,
                    job_kind=claimed.job_kind,
                    status="running",
                )
                self._connection.execute(
                    """
insert into portfell_app.job_attempts (job_attempt_id, job_id, attempt_number, worker_id)
select %s::uuid, job_id, attempt_count, %s
from portfell_app.jobs
where job_id = %s::uuid and lease_token = %s::uuid
""",
                    (str(uuid.uuid4()), worker_id, row[0], lease_token),
                )
        return tuple(_claimed_job(row, lease_token) for row in rows)

    def complete(
        self,
        *,
        job_id: str,
        lease_token: str,
        status: str,
        terminal_code: str | None = None,
    ) -> None:
        """Complete a leased job only when its current owner still holds the lease."""

        if status not in {"succeeded", "partial", "failed", "cancelled"}:
            raise DurableJobError("job_terminal_status_invalid")
        with self._connection.transaction():
            completed = self._connection.execute(
                """
update portfell_app.jobs
set status = %s, terminal_code = %s, lease_owner = null, lease_token = null,
    lease_expires_at = null, heartbeat_at = now(), updated_at = now()
where job_id = %s::uuid and status = 'running' and lease_token = %s::uuid
returning job_id::text, user_id::text, job_kind, status
""",
                (status, terminal_code, job_id, lease_token),
            ).fetchone()
            if completed is None:
                raise DurableJobError("job_lease_lost")
            completed_job_id, user_id, job_kind, completed_status = _completed_job(completed)
            self._sync_initial_fill_status(
                job_id=completed_job_id,
                user_id=user_id,
                job_kind=job_kind,
                status=_initial_fill_status(completed_status),
            )
            self._connection.execute(
                """
update portfell_app.job_attempts
set finished_at = now(), terminal_code = %s
where job_id = %s::uuid and attempt_number = (
    select attempt_count from portfell_app.jobs where job_id = %s::uuid
)
""",
                (terminal_code, job_id, job_id),
            )

    def heartbeat(self, *, job_id: str, lease_token: str) -> None:
        """Extend only the currently owned running-job lease."""

        with self._connection.transaction():
            updated = self._connection.execute(
                """
update portfell_app.jobs
set heartbeat_at = now(), lease_expires_at = now() + interval '5 minutes', updated_at = now()
where job_id = %s::uuid and status = 'running' and lease_token = %s::uuid
returning job_id
""",
                (job_id, lease_token),
            ).fetchone()
            if updated is None:
                raise DurableJobError("job_lease_lost")

    def update_progress(
        self, *, job_id: str, lease_token: str, completed_units: int, total_units: int
    ) -> None:
        """Persist bounded progress only for the worker that still owns the lease."""

        if completed_units < 0 or total_units < 0 or completed_units > total_units:
            raise DurableJobError("job_progress_invalid")
        with self._connection.transaction():
            updated = self._connection.execute(
                """
update portfell_app.jobs
set completed_units = %s, total_units = %s, heartbeat_at = now(),
    lease_expires_at = now() + interval '5 minutes', updated_at = now()
where job_id = %s::uuid and status = 'running' and lease_token = %s::uuid
returning job_id
""",
                (completed_units, total_units, job_id, lease_token),
            ).fetchone()
            if updated is None:
                raise DurableJobError("job_lease_lost")

    def recover_expired_leases(self) -> tuple[str, ...]:
        """Return expired running jobs to the queue and close their attempts."""

        with self._connection.transaction():
            rows = self._connection.execute(
                """
update portfell_app.jobs
set status = 'queued', lease_owner = null, lease_token = null, lease_expires_at = null,
    available_at = now(), updated_at = now()
where status = 'running' and lease_expires_at <= now()
returning job_id::text, user_id::text, job_kind
"""
            ).fetchall()
            recovered = tuple(_recovered_job(row) for row in rows)
            for job_id, user_id, job_kind in recovered:
                self._sync_initial_fill_status(
                    job_id=job_id,
                    user_id=user_id,
                    job_kind=job_kind,
                    status="planning",
                )
            job_ids = tuple(job_id for job_id, _, _ in recovered)
            for job_id in job_ids:
                self._connection.execute(
                    """
update portfell_app.job_attempts
set finished_at = now(), terminal_code = 'lease_expired'
where job_id = %s::uuid and finished_at is null
""",
                    (job_id,),
                )
        return job_ids

    def _sync_initial_fill_status(
        self, *, job_id: str, user_id: str, job_kind: str, status: str
    ) -> None:
        if job_kind != "project_initial_fill":
            return
        self._connection.execute(*set_authenticated_user_sql(user_id))
        self._connection.execute(
            """
update portfell_app.project_initial_fills
set status = %s, updated_at = now()
where bootstrap_job_id = %s::uuid
""",
            (status, job_id),
        )


def _claimed_job(row: tuple[object, ...], lease_token: str) -> ClaimedJob:
    if len(row) != 7 or any(not isinstance(value, str) for value in row[:6]):
        raise DurableJobError("job_claim_projection_invalid")
    if not isinstance(row[6], int):
        raise DurableJobError("job_claim_projection_invalid")
    job_id, user_id, project_id, job_kind, input_hash, input_ref = (str(value) for value in row[:6])
    return ClaimedJob(
        job_id,
        user_id,
        project_id,
        job_kind,
        input_hash,
        input_ref,
        row[6],
        lease_token,
    )


def _completed_job(row: tuple[object, ...]) -> tuple[str, str, str, str]:
    if len(row) != 4 or not all(isinstance(value, str) and value for value in row):
        raise DurableJobError("job_completion_projection_invalid")
    return str(row[0]), str(row[1]), str(row[2]), str(row[3])


def _recovered_job(row: tuple[object, ...]) -> tuple[str, str, str]:
    if len(row) != 3 or not all(isinstance(value, str) and value for value in row):
        raise DurableJobError("job_recovery_projection_invalid")
    return str(row[0]), str(row[1]), str(row[2])


def _initial_fill_status(job_status: str) -> str:
    statuses = {
        "succeeded": "ready",
        "partial": "partial",
        "failed": "failed",
        "cancelled": "failed",
    }
    try:
        return statuses[job_status]
    except KeyError as error:
        raise DurableJobError("job_terminal_status_invalid") from error
