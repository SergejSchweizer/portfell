from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from portfell.app_state.errors import (
    APP_STATE_CONFLICT,
    APP_STATE_INVALID_TRANSITION,
    AppStateError,
)
from portfell.app_state.migration import APP_STATE_MIGRATIONS
from portfell.app_state.migrations.v002_analysis_jobs import MIGRATION_V002
from portfell.app_state.repository import PostgresAppStateRepository
from portfell.app_state.schema import APP_STATE_TABLES

NOW = datetime(2026, 8, 31, 21, 0, tzinfo=UTC)
JOB = (
    "job-a",
    "univariate",
    "universe-a",
    None,
    "queued",
    None,
    0,
    None,
    None,
    0,
    None,
    None,
    NOW,
    None,
    None,
)
RUN_SUCCEEDED = (
    "run-a",
    "univariate",
    "succeeded",
    "snapshot-a",
    "universe-a",
    "logical-a",
    "algo-a",
    None,
    NOW,
    NOW,
    NOW,
)


class Cursor:
    def __init__(self, rows: list[Sequence[object]]) -> None:
        self.rows = rows

    def fetchone(self) -> Sequence[object] | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[Sequence[object]]:
        return list(self.rows)


class Connection:
    def __init__(self, rows: list[list[Sequence[object]]]) -> None:
        self.rows = list(rows)
        self.executed: list[tuple[str, Sequence[object] | None]] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, query: str, params: Sequence[object] | None = None) -> Cursor:
        self.executed.append((query, params))
        return Cursor(self.rows.pop(0) if self.rows else [])

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def repo(rows: list[list[Sequence[object]]]) -> tuple[PostgresAppStateRepository, Connection]:
    connection = Connection(rows)
    return PostgresAppStateRepository(connection), connection


def running_job(*, current: int = 0, total: int | None = None) -> tuple[object, ...]:
    row = list(JOB)
    row[4] = "running"
    row[6] = current
    row[7] = total
    row[8] = "work"
    row[9] = 1
    row[10] = NOW
    row[13] = NOW
    return tuple(row)


def succeeded_job() -> tuple[object, ...]:
    row = list(running_job(current=10, total=10))
    row[4] = "succeeded"
    row[5] = "run-a"
    row[14] = NOW
    return tuple(row)


def test_v2_migration_is_registered_without_rewriting_v1() -> None:
    assert tuple(migration.version for migration in APP_STATE_MIGRATIONS) == (1, 2)
    assert APP_STATE_MIGRATIONS[-1] is MIGRATION_V002
    assert "analysis_jobs" in APP_STATE_TABLES
    sql = MIGRATION_V002.sql
    assert "create table if not exists portfell.analysis_jobs" in sql
    assert "analysis_jobs_active_logical_idx" in sql
    assert "coalesce(requested_objective, '')" in sql
    assert "where status in ('queued', 'running')" in sql
    assert "analysis_runs" in sql
    assert "analysis_artifacts" not in MIGRATION_V002.destructive_down_sql


def test_create_or_get_active_job_is_atomic_and_small() -> None:
    repository, connection = repo([[], [JOB]])
    record = repository.create_or_get_active_job(
        job_id="job-a", stage="univariate", input_ref="universe-a"
    )
    assert record.job_id == "job-a"
    assert record.status == "queued"
    assert record.run_id is None
    assert connection.commits == 1
    assert "on conflict do nothing" in connection.executed[0][0]
    assert "status in ('queued', 'running')" in connection.executed[1][0]


def test_job_request_validation_is_fail_closed() -> None:
    repository, connection = repo([])
    invalid = (
        {"job_id": "", "stage": "univariate", "input_ref": "u"},
        {"job_id": "j", "stage": "metadata", "input_ref": "u"},
        {
            "job_id": "j",
            "stage": "univariate",
            "input_ref": "u",
            "requested_objective": "return_risk",
        },
        {"job_id": "j", "stage": "multivariate", "input_ref": "b"},
    )
    for values in invalid:
        with pytest.raises(AppStateError) as error:
            repository.create_or_get_active_job(**values)  # type: ignore[arg-type]
        assert error.value.code == APP_STATE_CONFLICT
    assert connection.executed == []


def test_claim_increments_attempt_and_rejects_second_live_claim() -> None:
    claimed = running_job()
    repository, connection = repo([[claimed]])
    record = repository.claim_job("job-a", stale_before=NOW - timedelta(minutes=5))
    assert record.status == "running"
    assert record.attempt == 1
    assert record.progress_current == 0
    assert connection.commits == 1
    assert "attempt = attempt + 1" in connection.executed[0][0]

    repository, connection = repo([[]])
    with pytest.raises(AppStateError) as error:
        repository.claim_job("job-a", stale_before=NOW - timedelta(minutes=5))
    assert error.value.code == APP_STATE_CONFLICT
    assert connection.rollbacks == 1


def test_progress_validation_and_monotone_update() -> None:
    repository, connection = repo([])
    invalid = ((-1, None, "work"), (2, 1, "work"), (0, -1, "work"), (0, None, " "))
    for current, total, phase in invalid:
        with pytest.raises(AppStateError) as error:
            repository.update_job_progress("job-a", current=current, total=total, phase=phase)
        assert error.value.code == APP_STATE_CONFLICT
    assert connection.executed == []

    repository, connection = repo([[running_job(current=3, total=10)]])
    record = repository.update_job_progress("job-a", current=3, total=10, phase="members")
    assert record.progress_current == 3
    assert record.progress_total == 10
    assert connection.commits == 1
    assert "progress_current <= %s" in connection.executed[0][0]

    repository, _ = repo([[]])
    with pytest.raises(AppStateError) as error:
        repository.update_job_progress("job-a", current=2, total=10, phase="members")
    assert error.value.code == APP_STATE_INVALID_TRANSITION


def test_terminal_job_rules_require_matching_succeeded_run() -> None:
    linked = list(running_job(current=10, total=10))
    linked[5] = "run-a"
    repository, connection = repo([[tuple(linked)], [RUN_SUCCEEDED], [succeeded_job()]])
    record = repository.complete_job("job-a", status="succeeded")
    assert record.status == "succeeded"
    assert connection.commits == 1

    repository, _ = repo([[running_job()]])
    with pytest.raises(AppStateError) as error:
        repository.complete_job("job-a", status="succeeded")
    assert error.value.code == APP_STATE_INVALID_TRANSITION

    repository, _ = repo([])
    with pytest.raises(AppStateError) as error:
        repository.complete_job("job-a", status="failed")
    assert error.value.code == APP_STATE_INVALID_TRANSITION


def test_list_jobs_is_parameterized_stably_ordered_and_bounded() -> None:
    repository, connection = repo([[JOB]])
    rows = repository.list_analysis_jobs(stage="univariate", status="queued", limit=7)
    assert rows[0].job_id == "job-a"
    query, params = connection.executed[0]
    assert "order by created_at desc, job_id" in query
    assert params == ("univariate", "queued", 7)

    with pytest.raises(AppStateError):
        repository.list_analysis_jobs(stage="metadata")
    with pytest.raises(AppStateError):
        repository.list_analysis_jobs(status="unknown")
