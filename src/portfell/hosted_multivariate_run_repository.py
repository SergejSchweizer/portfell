"""Durable Multivariate run persistence ports."""

from __future__ import annotations

import json
from typing import Protocol, cast

from portfell.hosted_api_state import HostedApiState, MultivariateRunRecord
from portfell.hosted_catalog import set_authenticated_user_sql
from portfell.table_io import JsonRow


class MultivariateRunCursor(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...


class MultivariateRunConnection(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> MultivariateRunCursor: ...


class MultivariateRunRepository(Protocol):
    def get(self, *, user_id: str, run_id: str) -> MultivariateRunRecord | None: ...

    def by_logical_hash(
        self, *, user_id: str, logical_hash: str
    ) -> MultivariateRunRecord | None: ...

    def current(self, *, user_id: str, project_id: str) -> MultivariateRunRecord | None: ...

    def save(
        self, run: MultivariateRunRecord, *, make_current: bool = False
    ) -> MultivariateRunRecord: ...


class LocalMultivariateRunRepository:
    """Explicit transition adapter for pre-cutover workspace state."""

    def __init__(self, state: HostedApiState) -> None:
        self._state = state

    def get(self, *, user_id: str, run_id: str) -> MultivariateRunRecord | None:
        run = self._state.multivariate_runs_by_id.get(run_id)
        return run if run is not None and run.user_id == user_id else None

    def by_logical_hash(self, *, user_id: str, logical_hash: str) -> MultivariateRunRecord | None:
        return next(
            (
                run
                for run in self._state.multivariate_runs_by_id.values()
                if run.user_id == user_id and run.logical_hash == logical_hash
            ),
            None,
        )

    def current(self, *, user_id: str, project_id: str) -> MultivariateRunRecord | None:
        run_id = self._state.current_multivariate_run_by_project.get(project_id)
        return None if run_id is None else self.get(user_id=user_id, run_id=run_id)

    def save(
        self, run: MultivariateRunRecord, *, make_current: bool = False
    ) -> MultivariateRunRecord:
        self._state.multivariate_runs_by_id[run.run_id] = run
        if make_current:
            self._state.current_multivariate_run_by_project[run.project_id] = run.run_id
        return run


class PostgresMultivariateRunRepository:
    """RLS-bound PostgreSQL storage of control data and bounded API result documents."""

    def __init__(self, connection: MultivariateRunConnection) -> None:
        self._connection = connection

    def get(self, *, user_id: str, run_id: str) -> MultivariateRunRecord | None:
        self._bind(user_id)
        return self._read("where multivariate_run_id = %s", (run_id,))

    def by_logical_hash(self, *, user_id: str, logical_hash: str) -> MultivariateRunRecord | None:
        self._bind(user_id)
        return self._read("where logical_hash = %s", (logical_hash,))

    def current(self, *, user_id: str, project_id: str) -> MultivariateRunRecord | None:
        self._bind(user_id)
        return self._read(
            "join portfell_app.current_multivariate_run_preferences as current "
            "on current.multivariate_run_id = run.multivariate_run_id "
            "where current.project_id = %s::uuid",
            (project_id,),
        )

    def save(
        self, run: MultivariateRunRecord, *, make_current: bool = False
    ) -> MultivariateRunRecord:
        self._bind(run.user_id)
        self._connection.execute(
            """
insert into portfell_app.multivariate_runs (
    multivariate_run_id, user_id, project_id, bivariate_run_id, input_snapshot_id,
    logical_hash, status, phase, completed_units, total_units, started_at_epoch, document
) values (%s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
on conflict (multivariate_run_id) do update set
    input_snapshot_id = excluded.input_snapshot_id,
    status = excluded.status,
    phase = excluded.phase,
    completed_units = excluded.completed_units,
    total_units = excluded.total_units,
    started_at_epoch = excluded.started_at_epoch,
    document = excluded.document,
    updated_at = now()
""",
            (*_fields(run), json.dumps(_document(run), sort_keys=True, separators=(",", ":"))),
        )
        if make_current:
            self._connection.execute(
                """
insert into portfell_app.current_multivariate_run_preferences (
    project_id, user_id, multivariate_run_id
) values (%s::uuid, %s::uuid, %s)
on conflict (project_id) do update set
    user_id = excluded.user_id,
    multivariate_run_id = excluded.multivariate_run_id,
    updated_at = now()
""",
                (run.project_id, run.user_id, run.run_id),
            )
        return run

    def _read(self, clause: str, parameters: tuple[object, ...]) -> MultivariateRunRecord | None:
        row = self._connection.execute(
            """
select run.multivariate_run_id, run.user_id::text, run.project_id::text,
       run.bivariate_run_id, run.input_snapshot_id, run.logical_hash, run.status,
       run.phase, run.completed_units, run.total_units, run.started_at_epoch, run.document
from portfell_app.multivariate_runs as run
"""
            + clause,
            parameters,
        ).fetchone()
        return None if row is None else _record(row)

    def _bind(self, user_id: str) -> None:
        self._connection.execute(*set_authenticated_user_sql(user_id))


def _fields(run: MultivariateRunRecord) -> tuple[object, ...]:
    return (
        run.run_id,
        run.user_id,
        run.project_id,
        run.bivariate_run_id,
        run.input_snapshot_id,
        run.logical_hash,
        run.status,
        run.phase,
        run.completed_units,
        run.total_units,
        run.started_at_epoch,
    )


def _document(run: MultivariateRunRecord) -> JsonRow:
    return {
        "settings": run.settings,
        "summary": run.summary,
        "structure": run.structure,
        "candidates": list(run.candidates),
        "validation": list(run.validation),
        "artifacts": run.artifacts,
        "components": list(run.components),
        "risk_contributions": list(run.risk_contributions),
        "income_evidence": list(run.income_evidence),
        "warnings": list(run.warnings),
        "failure_reason": run.failure_reason,
    }


def _record(row: tuple[object, ...]) -> MultivariateRunRecord:
    if (
        len(row) != 12
        or not all(isinstance(value, str) for value in row[:8])
        or not isinstance(row[8], int)
        or not isinstance(row[9], int)
        or not isinstance(row[10], float | int)
        or not isinstance(row[11], dict)
    ):
        raise ValueError("multivariate_run_projection_invalid")
    document = cast(JsonRow, row[11])
    return MultivariateRunRecord(
        run_id=cast(str, row[0]),
        user_id=cast(str, row[1]),
        project_id=cast(str, row[2]),
        bivariate_run_id=cast(str, row[3]),
        input_snapshot_id=cast(str, row[4]),
        logical_hash=cast(str, row[5]),
        status=cast(str, row[6]),
        phase=cast(str, row[7]),
        completed_units=row[8],
        total_units=row[9],
        started_at_epoch=float(row[10]),
        settings=_document_mapping(document, "settings"),
        summary=_document_mapping(document, "summary"),
        structure=_document_mapping(document, "structure"),
        candidates=_document_rows(document, "candidates"),
        validation=_document_rows(document, "validation"),
        artifacts=_document_mapping(document, "artifacts"),
        components=_document_rows(document, "components"),
        risk_contributions=_document_rows(document, "risk_contributions"),
        income_evidence=_document_rows(document, "income_evidence"),
        warnings=_document_strings(document, "warnings"),
        failure_reason=_document_optional_string(document, "failure_reason"),
    )


def _document_mapping(document: JsonRow, key: str) -> JsonRow:
    value = document.get(key, {})
    if not isinstance(value, dict):
        raise ValueError("multivariate_run_projection_invalid")
    return dict(cast(JsonRow, value))


def _document_rows(document: JsonRow, key: str) -> tuple[JsonRow, ...]:
    value = document.get(key, [])
    values = cast(list[object], value) if isinstance(value, list) else None
    if values is None or not all(isinstance(item, dict) for item in values):
        raise ValueError("multivariate_run_projection_invalid")
    return tuple(dict(cast(JsonRow, item)) for item in values)


def _document_strings(document: JsonRow, key: str) -> tuple[str, ...]:
    value = document.get(key, [])
    values = cast(list[object], value) if isinstance(value, list) else None
    if values is None or not all(isinstance(item, str) for item in values):
        raise ValueError("multivariate_run_projection_invalid")
    return tuple(cast(str, item) for item in values)


def _document_optional_string(document: JsonRow, key: str) -> str | None:
    value = document.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError("multivariate_run_projection_invalid")
    return value
