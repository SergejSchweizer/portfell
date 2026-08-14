"""Bounded PostgreSQL read/write adapter for one project workflow projection."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol, cast

from portfell.hosted_catalog import set_authenticated_user_sql

JsonRow = dict[str, Any]


class ProjectWorkflowCursor(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...


class ProjectWorkflowConnection(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> ProjectWorkflowCursor: ...


class PostgresProjectWorkflowProjection:
    """Read and idempotently write one authorized compact workflow payload."""

    def __init__(self, connection: ProjectWorkflowConnection) -> None:
        self._connection = connection

    def read(self, *, user_id: str, project_id: str) -> tuple[JsonRow, str] | None:
        self._connection.execute(*set_authenticated_user_sql(user_id))
        row = self._connection.execute(
            """
select payload, projection_revision
from portfell_app.project_workflow_projections
where user_id = %s::uuid and project_id = %s::uuid
""",
            (user_id, project_id),
        ).fetchone()
        if row is None:
            return None
        return _projection(row)

    def write(self, *, user_id: str, project_id: str, payload: JsonRow) -> tuple[JsonRow, str]:
        self._connection.execute(*set_authenticated_user_sql(user_id))
        row = self._connection.execute(
            """
insert into portfell_app.project_workflow_projections (
    project_id, user_id, payload, projection_revision
) values (%s::uuid, %s::uuid, %s::jsonb, 1)
on conflict (project_id) do update
set payload = excluded.payload,
    projection_revision = case
        when portfell_app.project_workflow_projections.payload is distinct from excluded.payload
        then portfell_app.project_workflow_projections.projection_revision + 1
        else portfell_app.project_workflow_projections.projection_revision
    end,
    updated_at = case
        when portfell_app.project_workflow_projections.payload is distinct from excluded.payload
        then now()
        else portfell_app.project_workflow_projections.updated_at
    end
where portfell_app.project_workflow_projections.user_id = excluded.user_id
returning payload, projection_revision
""",
            (project_id, user_id, json.dumps(payload, sort_keys=True, separators=(",", ":"))),
        ).fetchone()
        if row is None:
            raise ValueError("project_workflow_projection_not_owned")
        return _projection(row)


def _projection(row: tuple[object, ...]) -> tuple[JsonRow, str]:
    if len(row) != 2 or not isinstance(row[0], dict) or not isinstance(row[1], int):
        raise ValueError("project_workflow_projection_invalid")
    payload = cast(JsonRow, row[0])
    encoded = json.dumps(
        {"payload": payload, "revision": row[1]}, sort_keys=True, separators=(",", ":")
    ).encode()
    return payload, hashlib.sha256(encoded).hexdigest()
