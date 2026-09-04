"""PR411 durable command and lease contract tests."""

from __future__ import annotations

import pytest

from portfell.app_state.migration import APP_STATE_MIGRATIONS
from portfell.app_state.migrations import MIGRATION_V005
from portfell_contracts import JobProgress, JobStatus, Stage
from portfell_workflow import WorkflowCommand, WorkflowCommandRepository


class Cursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = iter(rows)

    def fetchone(self) -> tuple[object, ...] | None:
        return next(self.rows, None)


class Connection:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.commits = 0
        self.rollbacks = 0
        self.next_rows: list[tuple[object, ...]] = []

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> Cursor:
        self.queries.append(query)
        return Cursor(self.next_rows)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def command() -> WorkflowCommand:
    return WorkflowCommand("cmd-1", Stage.UNIVARIATE, "selection-1", "compute", "v1", "idem-1")


def test_v005_adds_restart_safe_progress_and_lease_columns() -> None:
    assert APP_STATE_MIGRATIONS[-1] is MIGRATION_V005
    assert "lease_expires_at" in MIGRATION_V005.sql
    assert "progress_current" in MIGRATION_V005.sql
    assert "create index if not exists workflow_stage_commands_claim_idx" in MIGRATION_V005.sql


def test_enqueue_uses_idempotency_and_only_id_fields() -> None:
    connection = Connection()
    connection.next_rows = [("cmd-1", "univariate", "selection-1", "compute", "v1", "idem-1")]
    result = WorkflowCommandRepository(connection).enqueue(command())
    assert result == command()
    sql = connection.queries[0].casefold()
    assert "on conflict (idempotency_key)" in sql
    for forbidden in ("quote", "covariance", "matrix", "portfolio"):
        assert forbidden not in sql


def test_claim_uses_postgresql_row_lock_and_skip_locked() -> None:
    connection = Connection()
    connection.next_rows = [("cmd-1", "univariate", "selection-1", "compute", "v1", "idem-1")]
    result = WorkflowCommandRepository(connection).claim(worker_id="worker-1")
    assert result == command()
    assert "for update skip locked" in connection.queries[0].casefold()


def test_progress_update_and_stale_recovery_commit() -> None:
    connection = Connection()
    repository = WorkflowCommandRepository(connection)
    repository.update_progress(
        "cmd-1", JobProgress(Stage.UNIVARIATE, JobStatus.RUNNING, "metrics", 2, 5)
    )
    connection.next_rows = [("cmd-1",)]
    assert repository.recover_stale() == 1
    assert connection.commits == 2


def test_invalid_command_and_invalid_claim_fail_before_database_access() -> None:
    with pytest.raises(ValueError):
        WorkflowCommand("", Stage.UNIVARIATE, "x", "compute", "v1", "i")
    with pytest.raises(ValueError):
        WorkflowCommand("c", Stage.GATEWAY, "x", "compute", "v1", "i")
    with pytest.raises(ValueError):
        WorkflowCommandRepository(Connection()).claim(worker_id="", lease_seconds=0)
