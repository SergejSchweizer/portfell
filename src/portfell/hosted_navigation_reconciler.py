"""Deterministic repair and command-side rebuild for navigation projections."""

from __future__ import annotations

from typing import Any, Protocol, cast

from portfell.hosted_catalog import set_authenticated_user_sql
from portfell.hosted_navigation_read_model_repository import PostgresNavigationReadModel

JsonRow = dict[str, Any]


class NavigationReconciliationCursor(Protocol):
    """Minimal cursor used by the bounded reconciliation query."""

    def fetchone(self) -> tuple[object, ...] | None: ...


class NavigationReconciliationConnection(Protocol):
    """Connection supplied by a caller that owns the transaction boundary."""

    def execute(
        self, sql: str, parameters: tuple[object, ...] = ()
    ) -> NavigationReconciliationCursor: ...


class PostgresNavigationReconciler:
    """Rebuild one user's compact navigation projection from PostgreSQL control state."""

    def __init__(self, connection: NavigationReconciliationConnection) -> None:
        self._connection = connection
        self._writer = PostgresNavigationReadModel(connection)

    def reconcile(self, user_id: str) -> tuple[JsonRow, str]:
        """Return the canonical projection after an idempotent same-transaction upsert."""

        self._connection.execute(*set_authenticated_user_sql(user_id))
        row = self._connection.execute(
            """
with project_rows as (
    select project.project_id::text as project_id,
           project.name,
           selection.selection_version_id::text as selection_id,
           count(distinct member.isin)::integer as selected_count,
           coalesce(fill.status = 'ready', false) as data_loaded
    from portfell_app.projects as project
    left join portfell_app.project_selection_versions as selection
      on selection.project_id = project.project_id
     and selection.membership_sealed_at is not null
    left join portfell_app.project_selection_members as member
      on member.selection_version_id = selection.selection_version_id
    left join portfell_app.project_initial_fills as fill
      on fill.project_id = project.project_id
    where project.user_id = %s::uuid
      and project.status = 'active'
    group by project.project_id, project.name, selection.selection_version_id, fill.status
), navigation as (
    select coalesce(
        jsonb_agg(
            jsonb_strip_nulls(
                jsonb_build_object(
                    'project_id', project_id,
                    'name', name,
                    'selection_id', selection_id,
                    'selected_count', selected_count,
                    'data_loaded', data_loaded
                )
            ) order by lower(name), project_id
        ),
        '[]'::jsonb
    ) as projects
    from project_rows
), preference as (
    select current.project_id::text as project_id
    from portfell_app.current_project_preferences as current
    join portfell_app.projects as project
      on project.project_id = current.project_id
     and project.status = 'active'
    where current.user_id = %s::uuid
)
select jsonb_build_object(
    'current_project_id', preference.project_id,
    'current_project', (
        select jsonb_strip_nulls(
            jsonb_build_object(
                'project_id', project.project_id,
                'name', project.name,
                'selection_id', project.selection_id,
                'selected_count', project.selected_count,
                'data_loaded', project.data_loaded
            )
        )
        from project_rows as project
        where project.project_id = preference.project_id
    ),
    'projects', navigation.projects
)
from navigation
left join preference on true
""",
            (user_id, user_id),
        ).fetchone()
        if row is None or len(row) != 1 or not isinstance(row[0], dict):
            raise ValueError("navigation_reconciliation_invalid")
        return self._writer.write(user_id, cast(JsonRow, row[0]))
