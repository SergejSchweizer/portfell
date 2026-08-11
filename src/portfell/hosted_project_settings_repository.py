"""Project-scoped UI settings port with PostgreSQL and explicit local adapters."""

from __future__ import annotations

import json
from typing import Protocol, cast

from portfell.hosted_api_state import HostedApiState
from portfell.hosted_catalog import set_authenticated_user_sql
from portfell.table_io import JsonRow

DEFAULT_UNIVARIATE_SELECTION_SETTINGS: JsonRow = {
    "dividend_frequencies": [],
    "statistic_labels": {},
    "statistic_ranges": {},
}


class ProjectSettingsCursor(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...


class ProjectSettingsConnection(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> ProjectSettingsCursor: ...


class ProjectSettingsRepository(Protocol):
    def univariate(self, *, user_id: str, project_id: str) -> JsonRow: ...

    def save_univariate(self, *, user_id: str, project_id: str, settings: JsonRow) -> JsonRow: ...


class LocalProjectSettingsRepository:
    """Temporary explicit adapter for test/local state during the cutover stack."""

    def __init__(self, state: HostedApiState) -> None:
        self._state = state

    def univariate(self, *, user_id: str, project_id: str) -> JsonRow:
        del user_id
        return _normalise(self._state.univariate_selection_settings_by_project.get(project_id, {}))

    def save_univariate(self, *, user_id: str, project_id: str, settings: JsonRow) -> JsonRow:
        del user_id
        value = _normalise(settings)
        self._state.univariate_selection_settings_by_project[project_id] = value
        return value


class PostgresProjectSettingsRepository:
    """RLS-bound durable persistence for project-owned UI selections."""

    def __init__(self, connection: ProjectSettingsConnection) -> None:
        self._connection = connection

    def univariate(self, *, user_id: str, project_id: str) -> JsonRow:
        self._bind(user_id)
        row = self._connection.execute(
            "select settings from portfell_app.project_univariate_settings "
            "where project_id = %s::uuid",
            (project_id,),
        ).fetchone()
        if row is None:
            return _normalise({})
        if len(row) != 1 or not isinstance(row[0], dict):
            raise ValueError("project_univariate_settings_projection_invalid")
        return _normalise(cast(JsonRow, row[0]))

    def save_univariate(self, *, user_id: str, project_id: str, settings: JsonRow) -> JsonRow:
        value = _normalise(settings)
        self._bind(user_id)
        self._connection.execute(
            """
insert into portfell_app.project_univariate_settings (project_id, user_id, settings)
values (%s::uuid, %s::uuid, %s::jsonb)
on conflict (project_id) do update
set settings = excluded.settings, updated_at = now()
""",
            (project_id, user_id, json.dumps(value, sort_keys=True, separators=(",", ":"))),
        )
        return value

    def _bind(self, user_id: str) -> None:
        self._connection.execute(*set_authenticated_user_sql(user_id))


def _normalise(settings: JsonRow) -> JsonRow:
    return {**DEFAULT_UNIVARIATE_SELECTION_SETTINGS, **dict(settings)}
