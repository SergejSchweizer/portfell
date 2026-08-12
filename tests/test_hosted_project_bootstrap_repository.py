from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from portfell.hosted_project_bootstrap_repository import PostgresProjectBootstrapRepository

USER_ID = "00000000-0000-5000-8000-000000000001"
PROJECT_ID = "00000000-0000-5000-8000-000000000010"
SELECTION_ID = "00000000-0000-5000-8000-000000000011"


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
    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple[object, ...]]] = []
        self.fill: tuple[object, ...] | None = None
        self.fill_status = "not_started"
        self.members = (("DE0000000001", "XETRA", "AAA"), ("US0000000002", "NYSE", "BBB"))

    def transaction(self) -> Any:
        return nullcontext()

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.statements.append((sql, parameters))
        if "from portfell_app.project_initial_fills" in sql:
            if self.fill is None:
                return _Cursor(rows=[])
            project_id, user_id, selection_id, membership_hash, count, job_id = self.fill
            return _Cursor(
                rows=[
                    (
                        user_id,
                        project_id,
                        selection_id,
                        membership_hash,
                        count,
                        self.fill_status,
                        job_id,
                        *member,
                    )
                    for member in self.members
                ]
            )
        if "insert into portfell_app.jobs" in sql:
            return _Cursor(row=(parameters[0],))
        if "from portfell_app.jobs" in sql:
            return _Cursor(row=("queued", 0, 2, None, 1_786_000_000, 1_786_000_001))
        if "insert into portfell_app.project_initial_fills" in sql:
            project_id, user_id, selection_id, membership_hash, count, job_id = parameters
            self.fill = (project_id, user_id, selection_id, membership_hash, count, job_id)
        return _Cursor()


def test_postgres_bootstrap_freezes_membership_and_enqueues_one_job() -> None:
    connection = _Connection()
    repository = PostgresProjectBootstrapRepository(connection)
    members = ("US0000000002:NYSE:BBB", "DE0000000001:XETRA:AAA")

    first = repository.start(
        user_id=USER_ID,
        project_id=PROJECT_ID,
        selection_id=SELECTION_ID,
        member_ids=members,
    )
    second = repository.start(
        user_id=USER_ID,
        project_id=PROJECT_ID,
        selection_id=SELECTION_ID,
        member_ids=members,
    )

    assert first == second
    assert first.bootstrap.member_ids == tuple(sorted(members))
    assert first.bootstrap.selected_listing_count == 2
    assert sum("insert into portfell_app.jobs" in sql for sql, _ in connection.statements) == 1
    fill_inserts = sum(
        "insert into portfell_app.project_initial_fills" in sql for sql, _ in connection.statements
    )
    assert fill_inserts == 1

    status = repository.status(user_id=USER_ID, project_id=PROJECT_ID)

    assert status is not None
    assert status.status == "planning"
    assert (status.completed_units, status.total_units, status.terminal_code) == (0, 2, None)
    assert status.started_at_epoch == 1_786_000_000
    assert status.last_progress_at_epoch == 1_786_000_001


def test_postgres_bootstrap_requeues_failed_initial_fill() -> None:
    connection = _Connection()
    repository = PostgresProjectBootstrapRepository(connection)
    members = ("DE0000000001:XETRA:AAA", "US0000000002:NYSE:BBB")
    repository.start(
        user_id=USER_ID,
        project_id=PROJECT_ID,
        selection_id=SELECTION_ID,
        member_ids=members,
    )
    connection.fill_status = "failed"

    retried = repository.start(
        user_id=USER_ID,
        project_id=PROJECT_ID,
        selection_id=SELECTION_ID,
        member_ids=members,
    )

    assert retried.bootstrap.status == "not_started"
    assert sum("set status = 'queued'" in sql for sql, _ in connection.statements) == 1
    assert sum("set status = 'not_started'" in sql for sql, _ in connection.statements) == 1
