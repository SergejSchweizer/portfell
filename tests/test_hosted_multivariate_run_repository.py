from __future__ import annotations

import json

from portfell.hosted_api_state import MultivariateRunRecord
from portfell.hosted_multivariate_run_repository import PostgresMultivariateRunRepository


class _Cursor:
    def __init__(self, row: tuple[object, ...] | None = None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        return _Cursor()


def _run() -> MultivariateRunRecord:
    return MultivariateRunRecord(
        run_id="multivariate-run-1",
        user_id="00000000-0000-5000-8000-000000000001",
        project_id="00000000-0000-5000-8000-000000000101",
        bivariate_run_id="bivariate-run-1",
        input_snapshot_id="snapshot-1",
        logical_hash="logical-hash-1",
        status="complete",
        phase="complete",
        completed_units=6,
        total_units=6,
        started_at_epoch=1.0,
        settings={},
        summary={"portfolio_count": 1},
        structure={"effective_rank": 2.0},
        candidates=({"candidate_id": "candidate-1"},),
        validation=({"candidate_id": "candidate-1", "status": "complete"},),
        artifacts={"risk_model_id": "risk-1"},
        components=({"component": 1},),
        risk_contributions=({"candidate_id": "candidate-1", "value": 1.0},),
        income_evidence=({"isin": "IE00"},),
        warnings=("warning-1",),
    )


def test_postgres_multivariate_run_repository_writes_owned_document_and_current_pointer() -> None:
    connection = _Connection()
    run = _run()

    assert PostgresMultivariateRunRepository(connection).save(run, make_current=True) == run

    assert connection.calls[0] == (
        "select set_config(%s, %s, true)",
        ("portfell.current_user_id", run.user_id),
    )
    statement, parameters = connection.calls[1]
    assert "insert into portfell_app.multivariate_runs" in statement
    assert "started_at_epoch = excluded.started_at_epoch" in statement
    assert parameters[:11] == (
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
    document = json.loads(str(parameters[11]))
    assert document["candidates"] == [{"candidate_id": "candidate-1"}]
    assert document["warnings"] == ["warning-1"]
    assert "current_multivariate_run_preferences" in connection.calls[2][0]
    assert connection.calls[2][1] == (run.project_id, run.user_id, run.run_id)
