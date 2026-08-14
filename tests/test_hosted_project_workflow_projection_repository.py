from __future__ import annotations

from portfell.hosted_project_workflow_projection_repository import (
    PostgresProjectWorkflowProjection,
)


class _Cursor:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        if "insert into portfell_app.project_workflow_projections" in sql:
            return _Cursor(({"stages": {}}, 3))
        return _Cursor(({"stages": {}}, 3))


def test_project_workflow_projection_binds_rls_and_is_revisioned() -> None:
    connection = _Connection()
    repository = PostgresProjectWorkflowProjection(connection)
    user_id = "00000000-0000-0000-0000-000000000001"
    project_id = "00000000-0000-0000-0000-000000000002"

    read = repository.read(user_id=user_id, project_id=project_id)
    written = repository.write(user_id=user_id, project_id=project_id, payload={"stages": {}})

    assert read is not None and written[1]
    assert connection.calls[0] == (
        "select set_config(%s, %s, true)",
        ("portfell.current_user_id", user_id),
    )
    assert "project_workflow_projections" in connection.calls[1][0]
    assert "project_workflow_projections" in connection.calls[3][0]
    assert connection.calls[3][1][:2] == (project_id, user_id)
