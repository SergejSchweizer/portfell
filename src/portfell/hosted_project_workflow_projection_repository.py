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
        self._bind(user_id)
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

    def read_owned(self, *, user_id: str, project_id: str) -> tuple[JsonRow, str] | None | object:
        """Read one owned project, distinguishing an absent projection from an absent project."""

        self._bind(user_id)
        row = self._connection.execute(
            """
select projection.payload, projection.projection_revision
from portfell_app.projects as project
left join portfell_app.project_workflow_projections as projection
    on projection.project_id = project.project_id and projection.user_id = project.user_id
where project.user_id = %s::uuid and project.project_id = %s::uuid
""",
            (user_id, project_id),
        ).fetchone()
        if row is None:
            return ABSENT_PROJECT
        if len(row) != 2:
            raise ValueError("project_workflow_projection_invalid")
        return None if row[0] is None and row[1] is None else _projection(row)

    def read_current(self, *, user_id: str) -> tuple[JsonRow, str] | None:
        """Read the current project's workflow with one projection-only statement."""

        self._bind(user_id)
        row = self._connection.execute(
            """
select workflow.payload, workflow.projection_revision
from portfell_app.navigation_projections as navigation
join portfell_app.project_workflow_projections as workflow
    on workflow.project_id = nullif(navigation.payload ->> 'current_project_id', '')::uuid
    and workflow.user_id = navigation.user_id
where navigation.user_id = %s::uuid
""",
            (user_id,),
        ).fetchone()
        return None if row is None else _projection(row)

    def write(self, *, user_id: str, project_id: str, payload: JsonRow) -> tuple[JsonRow, str]:
        payload, revision, _ = self.write_with_change(
            user_id=user_id, project_id=project_id, payload=payload
        )
        return payload, revision

    def write_with_change(
        self, *, user_id: str, project_id: str, payload: JsonRow
    ) -> tuple[JsonRow, str, bool]:
        """Write the projection and identify a real, serialized state transition."""

        self._bind(user_id)
        row = self._connection.execute(
            """
with written as (
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
  and portfell_app.project_workflow_projections.payload is distinct from excluded.payload
returning payload, projection_revision, true as changed
)
select payload, projection_revision, changed from written
union all
select payload, projection_revision, false
from portfell_app.project_workflow_projections
where project_id = %s::uuid and user_id = %s::uuid
  and not exists (select 1 from written)
""",
            (
                project_id,
                user_id,
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                project_id,
                user_id,
            ),
        ).fetchone()
        if row is None:
            raise ValueError("project_workflow_projection_not_owned")
        return _projection_change(row)

    def _bind(self, user_id: str) -> None:
        if getattr(self._connection, "authenticated_user_id", None) == user_id:
            return
        self._connection.execute(*set_authenticated_user_sql(user_id))


def _projection(row: tuple[object, ...]) -> tuple[JsonRow, str]:
    if len(row) != 2 or not isinstance(row[0], dict) or not isinstance(row[1], int):
        raise ValueError("project_workflow_projection_invalid")
    payload = cast(JsonRow, row[0])
    encoded = json.dumps(
        {"payload": payload, "revision": row[1]}, sort_keys=True, separators=(",", ":")
    ).encode()
    return payload, hashlib.sha256(encoded).hexdigest()


def _projection_change(row: tuple[object, ...]) -> tuple[JsonRow, str, bool]:
    if len(row) != 3 or not isinstance(row[2], bool):
        raise ValueError("project_workflow_projection_invalid")
    payload, revision = _projection((row[0], row[1]))
    return payload, revision, row[2]


ABSENT_PROJECT = object()
