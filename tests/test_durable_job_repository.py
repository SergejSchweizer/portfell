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
        self.completion_succeeds = True
        self.heartbeat_succeeds = True

    def transaction(self):
        return nullcontext()

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        if "insert into portfell_app.jobs" in sql and "returning job_id" in sql:
            return _Cursor(("job-1",) if self._inserted else None)
        if "for update skip locked" in sql:
            return _Cursor(rows=self._rows)
        if "returning job_id::text, user_id::text, project_id::text, job_kind, status" in sql:
            return _Cursor(
                ("job-1", "user-1", "project-1", "project_initial_fill", "succeeded")
                if self.completion_succeeds
                else None
            )
        if "set completed_units = %s, total_units = %s" in sql:
            return _Cursor(
                ("job-1", "user-1", "project-1", "project_initial_fill")
                if self.completion_succeeds
                else None
            )
        if "where job_id = %s::uuid and status = 'running'" in sql:
            if "set heartbeat_at" in sql:
                return _Cursor(("job-1",) if self.heartbeat_succeeds else None)
            return _Cursor(("job-1",) if self.completion_succeeds else None)
        if "where status = 'running' and lease_expires_at <= now()" in sql:
            return _Cursor(rows=self._rows)
        return _Cursor()


def _job() -> DurableJob:
    return DurableJob("job-1", "user-1", "project-1", "quote_delta", "hash-1", "input-1")


def _event() -> OutboxEvent:
    return OutboxEvent("event-1", "user-1", "job_queued", "job-1")


class _StatusEvents:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def append(self, **kwargs: object) -> None:
        self.events.append(kwargs)


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


def test_initial_fill_lifecycle_publishes_compact_events_in_the_job_transaction() -> None:
    events = _StatusEvents()
    connection = _Connection(
        rows=[("job-1", "user-1", "project-1", "project_initial_fill", "hash-1", "input-1", 2)]
    )
    repository = PostgresDurableJobRepository(connection, status_events=events)
    job = DurableJob("job-1", "user-1", "project-1", "project_initial_fill", "hash-1", "input-1")

    repository.enqueue(
        job=job,
        event=OutboxEvent("event-1", "user-1", "project_initial_fill.queued", "job-1"),
    )
    claimed = repository.claim(worker_id="worker-1", batch_size=1)
    repository.update_progress(
        job_id=claimed[0].job_id,
        lease_token=claimed[0].lease_token,
        completed_units=1,
        total_units=2,
    )
    repository.complete(job_id="job-1", lease_token=claimed[0].lease_token, status="succeeded")

    assert [event["event_type"] for event in events.events] == [
        "bootstrap.queued",
        "bootstrap.running",
        "bootstrap.progress",
        "bootstrap.completed",
    ]
    assert all(event["project_id"] == "project-1" for event in events.events)
    assert events.events[-1]["terminal_status"] == "succeeded"


def test_claim_uses_skip_locked_and_creates_one_attempt_per_claim() -> None:
    connection = _Connection(
        rows=[("job-1", "user-1", "project-1", "quote_delta", "hash-1", "input-1", 2)]
    )

    claimed = PostgresDurableJobRepository(connection).claim(worker_id="worker-1", batch_size=2)

    assert claimed[0].job_id == "job-1"
    assert claimed[0].lease_token
    statements = "\n".join(statement for statement, _ in connection.calls)
    assert "for update skip locked" in statements
    assert "select max(attempt.attempt_number)" in statements
    assert "insert into portfell_app.job_attempts" in statements


@pytest.mark.parametrize("worker_id, batch_size", [("", 1), ("worker-1", 0)])
def test_claim_rejects_invalid_worker_or_batch(worker_id: str, batch_size: int) -> None:
    with pytest.raises(DurableJobError, match="job_claim_invalid"):
        PostgresDurableJobRepository(_Connection()).claim(
            worker_id=worker_id, batch_size=batch_size
        )


def test_complete_uses_lease_compare_and_set_and_finishes_attempt() -> None:
    connection = _Connection()

    PostgresDurableJobRepository(connection).complete(
        job_id="job-1", lease_token="lease-1", status="succeeded"
    )

    statements = "\n".join(statement for statement, _ in connection.calls)
    assert "status = 'running' and lease_token = %s::uuid" in statements
    assert "update portfell_app.job_attempts" in statements


def test_terminal_initial_fill_transition_refreshes_navigation_in_transaction() -> None:
    refreshed: list[str] = []
    workflow_refreshed: list[tuple[str, str]] = []
    connection = _Connection()
    repository = PostgresDurableJobRepository(
        connection,
        navigation_refresher=refreshed.append,
        workflow_refresher=lambda user_id, project_id: workflow_refreshed.append(
            (user_id, project_id)
        ),
    )

    repository.complete(job_id="job-1", lease_token="lease-1", status="succeeded")

    assert refreshed == ["user-1"]
    assert workflow_refreshed == [("user-1", "project-1")]


def test_complete_rejects_stale_worker_lease() -> None:
    connection = _Connection()
    connection.completion_succeeds = False

    with pytest.raises(DurableJobError, match="job_lease_lost"):
        PostgresDurableJobRepository(connection).complete(
            job_id="job-1", lease_token="stale-lease", status="succeeded"
        )


def test_heartbeat_extends_only_the_current_worker_lease() -> None:
    connection = _Connection()

    PostgresDurableJobRepository(connection).heartbeat(job_id="job-1", lease_token="lease-1")

    assert "lease_expires_at = now() + interval '5 minutes'" in connection.calls[0][0]


def test_progress_is_bounded_and_requires_the_current_worker_lease() -> None:
    connection = _Connection()
    repository = PostgresDurableJobRepository(connection)

    repository.update_progress(
        job_id="job-1", lease_token="lease-1", completed_units=2, total_units=3
    )

    assert "set completed_units = %s, total_units = %s" in connection.calls[0][0]
    assert "lease_expires_at = now() + interval '5 minutes'" in connection.calls[0][0]
    with pytest.raises(DurableJobError, match="job_progress_invalid"):
        repository.update_progress(
            job_id="job-1", lease_token="lease-1", completed_units=4, total_units=3
        )


def test_expired_leases_return_jobs_to_queue_and_finish_attempts() -> None:
    connection = _Connection(rows=[("job-1", "user-1", "project-1", "project_initial_fill")])

    assert PostgresDurableJobRepository(connection).recover_expired_leases() == ("job-1",)

    statements = "\n".join(statement for statement, _ in connection.calls)
    assert "set status = 'queued'" in statements
    assert "terminal_code = 'lease_expired'" in statements


def test_project_initial_fill_projection_tracks_job_transitions() -> None:
    claim_connection = _Connection(
        rows=[("job-1", "user-1", "project-1", "project_initial_fill", "hash-1", "input-1", 2)]
    )
    completion_connection = _Connection()
    recovery_connection = _Connection(
        rows=[("job-1", "user-1", "project-1", "project_initial_fill")]
    )

    PostgresDurableJobRepository(claim_connection).claim(worker_id="worker-1", batch_size=1)
    PostgresDurableJobRepository(completion_connection).complete(
        job_id="job-1", lease_token="lease-1", status="succeeded"
    )
    PostgresDurableJobRepository(recovery_connection).recover_expired_leases()

    statements = "\n".join(
        statement
        for connection in (claim_connection, completion_connection, recovery_connection)
        for statement, _ in connection.calls
    )
    assert "set status = 'running'" in statements
    assert "returning job_id::text, user_id::text, project_id::text, job_kind, status" in statements
    assert "set status = %s, updated_at = now()" in statements
    assert sum("select set_config" in statement for statement, _ in claim_connection.calls) == 1
    assert (
        sum("select set_config" in statement for statement, _ in completion_connection.calls) == 1
    )
    assert sum("select set_config" in statement for statement, _ in recovery_connection.calls) == 1
    assert statements.count("update portfell_app.project_initial_fills") == 3


def test_durable_job_repository_rejects_invalid_identity_status_and_lost_heartbeat() -> None:
    repository = PostgresDurableJobRepository(_Connection())
    with pytest.raises(DurableJobError, match="job_outbox_identity_invalid"):
        repository.enqueue(job=_job(), event=OutboxEvent("event-1", "user-2", "queued", "job-1"))
    with pytest.raises(DurableJobError, match="job_terminal_status_invalid"):
        repository.complete(job_id="job-1", lease_token="lease-1", status="queued")
    connection = _Connection()
    connection.heartbeat_succeeds = False
    with pytest.raises(DurableJobError, match="job_lease_lost"):
        PostgresDurableJobRepository(connection).heartbeat(job_id="job-1", lease_token="lease-1")


def test_durable_job_repository_rejects_invalid_claim_and_recovery_projections() -> None:
    with pytest.raises(DurableJobError, match="job_claim_projection_invalid"):
        PostgresDurableJobRepository(
            _Connection(rows=[("job-1", "user-1", "project-1", "quote", "hash", "input", "high")])
        ).claim(worker_id="worker-1", batch_size=1)
    with pytest.raises(DurableJobError, match="job_recovery_projection_invalid"):
        PostgresDurableJobRepository(_Connection(rows=[(None,)])).recover_expired_leases()
