from __future__ import annotations

import json

from portfell.hosted_analysis_record_repository import PostgresAnalysisRecordRepository
from portfell.hosted_api_state import AnalysisRecord


class _Cursor:
    def fetchone(self) -> tuple[object, ...] | None:
        return None


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        return _Cursor()


def test_postgres_analysis_records_write_a_bounded_owned_result_document() -> None:
    record = AnalysisRecord(
        run_id="00000000-0000-5000-8000-000000000301",
        user_id="00000000-0000-5000-8000-000000000001",
        project_id="00000000-0000-5000-8000-000000000101",
        selection_id="00000000-0000-5000-8000-000000000201",
        logical_hash="analysis-hash",
        status="complete",
        metrics=({"name": "Sharpe", "value": 1.2},),
        returns=({"date": "2026-01-01", "value": 0.01},),
        weights=({"isin": "IE00", "weight": 1.0},),
        report={"summary": "complete"},
    )
    connection = _Connection()

    assert PostgresAnalysisRecordRepository(connection).save(record) == record

    assert connection.calls[0][1] == ("portfell.current_user_id", record.user_id)
    statement, parameters = connection.calls[1]
    assert "insert into portfell_app.hosted_analysis_records" in statement
    assert parameters[:6] == (
        record.run_id,
        record.user_id,
        record.project_id,
        record.selection_id,
        record.logical_hash,
        record.status,
    )
    assert json.loads(str(parameters[6])) == {
        "metrics": [{"name": "Sharpe", "value": 1.2}],
        "returns": [{"date": "2026-01-01", "value": 0.01}],
        "weights": [{"isin": "IE00", "weight": 1.0}],
        "report": {"summary": "complete"},
    }
