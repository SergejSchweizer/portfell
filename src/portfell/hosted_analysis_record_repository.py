"""Durable generic hosted analysis records."""

from __future__ import annotations

import json
from typing import Protocol, cast

from portfell.hosted_api_state import AnalysisRecord, HostedApiState
from portfell.hosted_catalog import set_authenticated_user_sql
from portfell.table_io import JsonRow


class AnalysisRecordCursor(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...


class AnalysisRecordConnection(Protocol):
    def execute(
        self, sql: str, parameters: tuple[object, ...] = ()
    ) -> AnalysisRecordCursor: ...


class AnalysisRecordRepository(Protocol):
    def get(self, *, user_id: str, run_id: str) -> AnalysisRecord | None: ...

    def save(self, record: AnalysisRecord) -> AnalysisRecord: ...


class LocalAnalysisRecordRepository:
    """Explicit transition adapter for the pre-cutover state object."""

    def __init__(self, state: HostedApiState) -> None:
        self._state = state

    def get(self, *, user_id: str, run_id: str) -> AnalysisRecord | None:
        record = self._state.analyses_by_id.get(run_id)
        return record if record is not None and record.user_id == user_id else None

    def save(self, record: AnalysisRecord) -> AnalysisRecord:
        self._state.analyses_by_id[record.run_id] = record
        return record


class PostgresAnalysisRecordRepository:
    """RLS-bound PostgreSQL storage for bounded generic analysis API results."""

    def __init__(self, connection: AnalysisRecordConnection) -> None:
        self._connection = connection

    def get(self, *, user_id: str, run_id: str) -> AnalysisRecord | None:
        self._bind(user_id)
        row = self._connection.execute(
            """
select analysis_record_id::text, user_id::text, project_id::text,
       selection_id::text, logical_hash, status, document
from portfell_app.hosted_analysis_records
where analysis_record_id = %s::uuid
""",
            (run_id,),
        ).fetchone()
        return None if row is None else _record(row)

    def save(self, record: AnalysisRecord) -> AnalysisRecord:
        self._bind(record.user_id)
        self._connection.execute(
            """
insert into portfell_app.hosted_analysis_records (
    analysis_record_id, user_id, project_id, selection_id, logical_hash, status, document
) values (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s::jsonb)
on conflict (analysis_record_id) do update set
    status = excluded.status,
    document = excluded.document,
    updated_at = now()
""",
            (
                record.run_id,
                record.user_id,
                record.project_id,
                record.selection_id,
                record.logical_hash,
                record.status,
                json.dumps(_document(record), sort_keys=True, separators=(",", ":")),
            ),
        )
        return record

    def _bind(self, user_id: str) -> None:
        self._connection.execute(*set_authenticated_user_sql(user_id))


def _document(record: AnalysisRecord) -> JsonRow:
    return {
        "metrics": list(record.metrics),
        "returns": list(record.returns),
        "weights": list(record.weights),
        "report": record.report,
    }


def _record(row: tuple[object, ...]) -> AnalysisRecord:
    if (
        len(row) != 7
        or not all(isinstance(value, str) for value in row[:6])
        or not isinstance(row[6], dict)
    ):
        raise ValueError("analysis_record_projection_invalid")
    document = cast(JsonRow, row[6])
    return AnalysisRecord(
        run_id=cast(str, row[0]),
        user_id=cast(str, row[1]),
        project_id=cast(str, row[2]),
        selection_id=cast(str, row[3]),
        logical_hash=cast(str, row[4]),
        status=cast(str, row[5]),
        metrics=_rows(document, "metrics"),
        returns=_rows(document, "returns"),
        weights=_rows(document, "weights"),
        report=_mapping(document, "report"),
    )


def _rows(document: JsonRow, key: str) -> tuple[JsonRow, ...]:
    value = document.get(key, [])
    values = cast(list[object], value) if isinstance(value, list) else None
    if values is None or not all(isinstance(item, dict) for item in values):
        raise ValueError("analysis_record_projection_invalid")
    return tuple(dict(cast(JsonRow, item)) for item in values)


def _mapping(document: JsonRow, key: str) -> JsonRow:
    value = document.get(key, {})
    if not isinstance(value, dict):
        raise ValueError("analysis_record_projection_invalid")
    return dict(cast(JsonRow, value))
