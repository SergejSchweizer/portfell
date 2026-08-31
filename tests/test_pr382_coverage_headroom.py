from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from portfell.app_services.research import ApplicationServiceError
from portfell.app_state.contracts import ListingIdentity, UnivariateSelectionRecord
from portfell.app_state.errors import (
    APP_STATE_CONFLICT,
    APP_STATE_INVALID_TRANSITION,
    APP_STATE_NOT_FOUND,
    APP_STATE_PERSISTENCE_FAILED,
    AppStateError,
)
from portfell.app_state.repository import PostgresAppStateRepository
from portfell.dash_app.callbacks import execute_action, persisted_browser_state
from portfell.dash_app.state import BrowserState, StageReadiness
from portfell.hosted_routes_research import research_router

NOW = datetime(2026, 8, 31, 20, 0, tzinfo=UTC)
RUN_ROW = (
    "run-a",
    "univariate",
    "succeeded",
    "snapshot-a",
    "universe-a",
    "logical-a",
    "algo-a",
    None,
    NOW,
    NOW,
    NOW,
)
ARTIFACT_ROW = ("artifact-a", "run-a", "summary", "hash-a", {"value": 1}, NOW)
DECISION_ROW = (
    "decision-a",
    "run-m",
    "return_risk",
    "candidate-a",
    "Mean Variance",
    "Mean Variance",
    True,
    True,
    None,
    {"score": 1},
    NOW,
)


class ScriptedCursor:
    def __init__(self, rows: list[Sequence[object]]) -> None:
        self._rows = rows

    def fetchone(self) -> Sequence[object] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[Sequence[object]]:
        return list(self._rows)


class ScriptedConnection:
    def __init__(self, rows: list[list[Sequence[object]]], *, fail_at: int | None = None) -> None:
        self._rows = list(rows)
        self._fail_at = fail_at
        self.executed: list[tuple[str, Sequence[object] | None]] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, query: str, params: Sequence[object] | None = None) -> ScriptedCursor:
        self.executed.append((query, params))
        if self._fail_at is not None and len(self.executed) == self._fail_at:
            raise RuntimeError("private database detail")
        rows = self._rows.pop(0) if self._rows else []
        return ScriptedCursor(rows)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _repository(
    rows: list[list[Sequence[object]]], *, fail_at: int | None = None
) -> tuple[PostgresAppStateRepository, ScriptedConnection]:
    connection = ScriptedConnection(rows, fail_at=fail_at)
    return PostgresAppStateRepository(connection), connection


def test_snapshot_repository_covers_existing_create_missing_and_failure() -> None:
    repository, connection = _repository([[("snap-a", "fp-a", NOW, NOW)]])
    existing = repository.put_market_source_snapshot(
        snapshot_id="ignored", source_fingerprint="fp-a", observed_at=NOW
    )
    assert existing.snapshot_id == "snap-a"
    assert connection.commits == 0

    repository, connection = _repository(
        [[], [], [("snap-b", "fp-b", NOW, NOW)]]
    )
    created = repository.put_market_source_snapshot(
        snapshot_id="snap-b", source_fingerprint="fp-b", observed_at=NOW
    )
    assert created.source_fingerprint == "fp-b"
    assert connection.commits == 1

    repository, _ = _repository([[]])
    with pytest.raises(AppStateError) as captured:
        repository.get_market_source_snapshot("missing")
    assert captured.value.code == APP_STATE_NOT_FOUND

    repository, connection = _repository([[], []], fail_at=2)
    with pytest.raises(AppStateError) as captured:
        repository.put_market_source_snapshot(
            snapshot_id="snap-c", source_fingerprint="fp-c", observed_at=NOW
        )
    assert captured.value.code == APP_STATE_PERSISTENCE_FAILED
    assert connection.rollbacks == 1
    assert "private database detail" not in str(captured.value)


def test_universe_repository_covers_list_missing_limits_and_member_validation() -> None:
    universe_row = ("u1", "s1", 2, "h1", NOW, NOW)
    repository, _ = _repository(
        [[universe_row], [("DE0001", "XETRA", "AAA")]]
    )
    listed = repository.list_metadata_universes(limit=1)
    assert listed[0].members == (ListingIdentity("DE0001", "XETRA", "AAA"),)

    repository, _ = _repository([[]])
    with pytest.raises(AppStateError) as captured:
        repository.get_metadata_universe("missing")
    assert captured.value.code == APP_STATE_NOT_FOUND

    repository, _ = _repository([])
    for invalid in (0, 501):
        with pytest.raises(AppStateError) as captured:
            repository.list_metadata_universes(limit=invalid)
        assert captured.value.code == APP_STATE_CONFLICT

    duplicate = ListingIdentity("DE0001", "XETRA", "AAA")
    repository, _ = _repository([[]])
    with pytest.raises(AppStateError) as captured:
        repository.create_metadata_universe(
            universe_id="dup",
            source_snapshot_id="s",
            version=1,
            content_hash="dup-hash",
            members=(duplicate, duplicate),
        )
    assert captured.value.code == APP_STATE_CONFLICT

    repository, _ = _repository([[]])
    with pytest.raises(AppStateError) as captured:
        repository.create_metadata_universe(
            universe_id="blank",
            source_snapshot_id="s",
            version=1,
            content_hash="blank-hash",
            members=(ListingIdentity(" ", "XETRA", "AAA"),),
        )
    assert captured.value.code == APP_STATE_CONFLICT


def test_analysis_run_repository_covers_validation_idempotency_and_transitions() -> None:
    repository, connection = _repository([])
    for stage, status in (("wrong", "queued"), ("univariate", "succeeded")):
        with pytest.raises(AppStateError) as captured:
            repository.create_analysis_run(
                run_id="run-x",
                stage=stage,
                status=status,
                input_snapshot_id="s",
                input_ref="u",
                logical_hash="h",
                algorithm_version="a",
            )
        assert captured.value.code == APP_STATE_INVALID_TRANSITION
    assert connection.executed == []

    repository, connection = _repository([[('run-a',)], [RUN_ROW]])
    existing = repository.create_analysis_run(
        run_id="different",
        stage="univariate",
        status="queued",
        input_snapshot_id="snapshot-a",
        input_ref="universe-a",
        logical_hash="logical-a",
        algorithm_version="algo-a",
    )
    assert existing.run_id == "run-a"
    assert connection.commits == 0

    running_row = list(RUN_ROW)
    running_row[2] = "running"
    running_row[10] = None
    repository, connection = _repository([[], [], [tuple(running_row)]])
    created = repository.create_analysis_run(
        run_id="run-a",
        stage="univariate",
        status="running",
        input_snapshot_id="snapshot-a",
        input_ref="universe-a",
        logical_hash="logical-a",
        algorithm_version="algo-a",
    )
    assert created.status == "running"
    assert connection.commits == 1

    repository, connection = _repository([[], []], fail_at=2)
    with pytest.raises(AppStateError) as captured:
        repository.create_analysis_run(
            run_id="run-fail",
            stage="univariate",
            status="queued",
            input_snapshot_id="s",
            input_ref="u",
            logical_hash="h",
            algorithm_version="a",
        )
    assert captured.value.code == APP_STATE_PERSISTENCE_FAILED
    assert connection.rollbacks == 1

    repository, _ = _repository([])
    for status, failure in (("queued", None), ("unknown", None), ("failed", None), ("succeeded", "x")):
        with pytest.raises(AppStateError) as captured:
            repository.transition_analysis_run(
                run_id="run-a", status=status, failure_code=failure
            )
        assert captured.value.code == APP_STATE_INVALID_TRANSITION

    running_row = list(RUN_ROW)
    running_row[2] = "running"
    running_row[10] = None
    repository, connection = _repository([[], [tuple(running_row)]])
    assert repository.transition_analysis_run(run_id="run-a", status="running").status == "running"
    assert connection.commits == 1

    failed_row = list(RUN_ROW)
    failed_row[2] = "failed"
    failed_row[7] = "calculation_failed"
    repository, connection = _repository([[], [tuple(failed_row)]])
    failed = repository.transition_analysis_run(
        run_id="run-a", status="failed", failure_code="calculation_failed"
    )
    assert failed.failure_code == "calculation_failed"
    assert connection.commits == 1

    repository, connection = _repository([[]], fail_at=1)
    with pytest.raises(AppStateError) as captured:
        repository.transition_analysis_run(run_id="run-a", status="succeeded")
    assert captured.value.code == APP_STATE_INVALID_TRANSITION
    assert connection.rollbacks == 1


def test_analysis_run_repository_covers_get_and_list_branches() -> None:
    repository, _ = _repository([[]])
    with pytest.raises(AppStateError) as captured:
        repository.get_analysis_run("missing")
    assert captured.value.code == APP_STATE_NOT_FOUND

    repository, _ = _repository([[RUN_ROW]])
    all_runs = repository.list_analysis_runs(limit=1)
    assert all_runs[0].logical_hash == "logical-a"

    repository, _ = _repository([[RUN_ROW]])
    staged = repository.list_analysis_runs(stage="univariate", limit=1)
    assert staged[0].stage == "univariate"

    repository, _ = _repository([])
    with pytest.raises(AppStateError) as captured:
        repository.list_analysis_runs(stage="invalid")
    assert captured.value.code == APP_STATE_NOT_FOUND


def test_artifact_repository_covers_create_list_failure_and_invalid_payload() -> None:
    repository, connection = _repository([[], [], [ARTIFACT_ROW]])
    created = repository.put_analysis_artifact(
        artifact_id="artifact-a",
        run_id="run-a",
        artifact_type="summary",
        content_hash="hash-a",
        document={"value": 1},
    )
    assert created.document == {"value": 1}
    assert connection.commits == 1

    repository, _ = _repository([[ARTIFACT_ROW]])
    assert repository.list_analysis_artifacts("run-a")[0].artifact_id == "artifact-a"

    repository, connection = _repository([[], []], fail_at=2)
    with pytest.raises(AppStateError) as captured:
        repository.put_analysis_artifact(
            artifact_id="artifact-b",
            run_id="run-a",
            artifact_type="rows",
            content_hash="hash-b",
            document={"value": 2},
        )
    assert captured.value.code == APP_STATE_PERSISTENCE_FAILED
    assert connection.rollbacks == 1

    invalid_artifact = ("a", "r", "t", "h", [1, 2], NOW)
    repository, _ = _repository([[invalid_artifact]])
    with pytest.raises(AppStateError) as captured:
        repository.list_analysis_artifacts("r")
    assert captured.value.code == APP_STATE_PERSISTENCE_FAILED


def test_selection_repository_covers_existing_create_list_and_missing() -> None:
    selection_row = ("sel-a", "run-a", 2, "hash-s", NOW, NOW)
    member = ("DE0001", "XETRA", "AAA")

    repository, connection = _repository([[('sel-a',)], [selection_row], [member]])
    existing = repository.create_univariate_selection(
        selection_id="ignored",
        source_run_id="run-a",
        version=9,
        content_hash="hash-s",
        members=(ListingIdentity(*member),),
    )
    assert existing.selection_id == "sel-a"
    assert connection.commits == 0

    repository, connection = _repository(
        [[], [], [], [selection_row], [member]]
    )
    created = repository.create_univariate_selection(
        selection_id="sel-a",
        source_run_id="run-a",
        version=2,
        content_hash="hash-s",
        members=(ListingIdentity(*member),),
    )
    assert created.members == (ListingIdentity(*member),)
    assert connection.commits == 1

    repository, _ = _repository([[selection_row], [member]])
    listed = repository.list_univariate_selections(limit=1)
    assert listed[0].version == 2

    repository, _ = _repository([[]])
    with pytest.raises(AppStateError) as captured:
        repository.get_univariate_selection("missing")
    assert captured.value.code == APP_STATE_NOT_FOUND


def test_decision_repository_covers_validation_idempotency_conflict_create_and_failure() -> None:
    repository, _ = _repository([])
    with pytest.raises(AppStateError) as captured:
        repository.put_decision_artifact(
            decision_id="d",
            run_id="r",
            objective="invalid",
            winning_candidate_id="c",
            requested_method="m",
            actual_method="m",
            available=True,
            production_eligible=True,
            reason=None,
            document={},
        )
    assert captured.value.code == APP_STATE_CONFLICT

    repository, connection = _repository([[DECISION_ROW]])
    existing = repository.put_decision_artifact(
        decision_id="ignored",
        run_id="run-m",
        objective="return_risk",
        winning_candidate_id="candidate-a",
        requested_method="Mean Variance",
        actual_method="Mean Variance",
        available=True,
        production_eligible=True,
        reason=None,
        document={"score": 1},
    )
    assert existing.decision_id == "decision-a"
    assert connection.commits == 0

    repository, _ = _repository([[DECISION_ROW]])
    with pytest.raises(AppStateError) as captured:
        repository.put_decision_artifact(
            decision_id="ignored",
            run_id="run-m",
            objective="return_risk",
            winning_candidate_id="candidate-b",
            requested_method="Mean Variance",
            actual_method="Mean Variance",
            available=True,
            production_eligible=True,
            reason=None,
            document={"score": 1},
        )
    assert captured.value.code == APP_STATE_CONFLICT

    repository, connection = _repository([[], [], [DECISION_ROW]])
    created = repository.put_decision_artifact(
        decision_id="decision-a",
        run_id="run-m",
        objective="return_risk",
        winning_candidate_id="candidate-a",
        requested_method="Mean Variance",
        actual_method="Mean Variance",
        available=True,
        production_eligible=True,
        reason=None,
        document={"score": 1},
    )
    assert created.winning_candidate_id == "candidate-a"
    assert connection.commits == 1

    repository, connection = _repository([[], []], fail_at=2)
    with pytest.raises(AppStateError) as captured:
        repository.put_decision_artifact(
            decision_id="decision-f",
            run_id="run-f",
            objective="minimum_risk",
            winning_candidate_id="candidate-a",
            requested_method="m",
            actual_method="m",
            available=False,
            production_eligible=False,
            reason="unavailable",
            document={},
        )
    assert captured.value.code == APP_STATE_PERSISTENCE_FAILED
    assert connection.rollbacks == 1

    repository, _ = _repository([[]])
    with pytest.raises(AppStateError) as captured:
        repository.get_decision_artifact("missing")
    assert captured.value.code == APP_STATE_NOT_FOUND


def test_ui_preference_repository_covers_upsert_reads_lists_and_failures() -> None:
    repository, connection = _repository([[], [("objective", "\"return_risk\"", NOW)]])
    record = repository.set_ui_preference("objective", "return_risk")
    assert record.value == "return_risk"
    assert connection.commits == 1

    repository, _ = _repository([[]])
    assert repository.get_ui_preference("missing") is None

    repository, _ = _repository([[("a", "1", NOW), ("b", '{"x":2}', NOW)]])
    listed = repository.list_ui_preferences()
    assert [item.value for item in listed] == [1, {"x": 2}]

    repository, connection = _repository([[]], fail_at=1)
    with pytest.raises(AppStateError) as captured:
        repository.set_ui_preference("x", True)
    assert captured.value.code == APP_STATE_PERSISTENCE_FAILED
    assert connection.rollbacks == 1

    repository, _ = _repository([[], []])
    with pytest.raises(AppStateError) as captured:
        repository.set_ui_preference("vanishing", None)
    assert captured.value.code == APP_STATE_NOT_FOUND


class RouteService:
    def __init__(self, *, failure: str | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def _fail(self) -> None:
        if self.failure is not None:
            raise ApplicationServiceError(self.failure)

    def run_univariate(self, universe_id: str) -> dict[str, object]:
        self._fail()
        self.calls.append(("univariate", (universe_id,), {}))
        return {"run_id": "uni-run", "status": "succeeded"}

    def create_univariate_selection(
        self, run_id: str, *, predicates: list[dict[str, object]] | None = None
    ) -> UnivariateSelectionRecord:
        self._fail()
        self.calls.append(("selection", (run_id,), {"predicates": predicates}))
        return UnivariateSelectionRecord(
            "selection-a",
            run_id,
            1,
            "selection-hash",
            NOW,
            NOW,
            (ListingIdentity("DE0001", "XETRA", "AAA"),),
        )

    def run_bivariate(self, selection_id: str) -> dict[str, object]:
        self._fail()
        self.calls.append(("bivariate", (selection_id,), {}))
        return {"run_id": "bi-run", "status": "succeeded"}

    def run_multivariate(
        self,
        *,
        selection_id: str,
        bivariate_run_id: str,
        objective: str = "return_risk",
    ) -> dict[str, object]:
        self._fail()
        self.calls.append(
            (
                "multivariate",
                (),
                {
                    "selection_id": selection_id,
                    "bivariate_run_id": bivariate_run_id,
                    "objective": objective,
                },
            )
        )
        return {"run_id": "multi-run", "status": "succeeded"}

    def run_detail(self, run_id: str) -> dict[str, object]:
        self._fail()
        self.calls.append(("detail", (run_id,), {}))
        return {"run_id": run_id}

    def stage_history(self, stage: str, *, limit: int = 100) -> tuple[dict[str, object], ...]:
        self._fail()
        self.calls.append(("history", (stage,), {"limit": limit}))
        return ({"run_id": "history-run", "stage": stage},)


def _route_client(service: RouteService) -> TestClient:
    app = FastAPI()
    app.include_router(research_router(service))
    return TestClient(app)


def test_research_routes_cover_successful_four_stage_flow_and_reads() -> None:
    service = RouteService()
    client = _route_client(service)

    assert client.post("/api/univariate/runs", json={"universe_id": "u1"}).json()["run_id"] == "uni-run"
    selection = client.post(
        "/api/univariate/selections",
        json={"run_id": "uni-run", "predicates": [{"metric": "sharpe_ratio", "min": 1.0}]},
    )
    assert selection.status_code == 200
    assert selection.json()["members"] == [
        {"isin": "DE0001", "exchange": "XETRA", "code": "AAA"}
    ]
    assert client.post("/api/bivariate/runs", json={"selection_id": "selection-a"}).status_code == 200
    multi = client.post(
        "/api/multivariate/runs",
        json={
            "selection_id": "selection-a",
            "bivariate_run_id": "bi-run",
            "objective": "minimum_risk",
        },
    )
    assert multi.status_code == 200
    assert client.get("/api/runs/multi-run").json() == {"run_id": "multi-run"}
    history = client.get("/api/runs", params={"stage": "univariate", "limit": 7})
    assert history.json()["total"] == 1
    assert service.calls[-1] == ("history", ("univariate",), {"limit": 7})


def test_research_routes_cover_defaults_and_validation_errors() -> None:
    service = RouteService()
    client = _route_client(service)

    response = client.post(
        "/api/univariate/selections", json={"run_id": "uni-run"}
    )
    assert response.status_code == 200
    assert service.calls[-1][2]["predicates"] is None

    response = client.post(
        "/api/multivariate/runs",
        json={"selection_id": "s", "bivariate_run_id": "b"},
    )
    assert response.status_code == 200
    assert service.calls[-1][2]["objective"] == "return_risk"

    invalid_payloads = (
        ("/api/univariate/runs", {}),
        ("/api/univariate/runs", {"universe_id": " "}),
        ("/api/bivariate/runs", {"selection_id": 3}),
        ("/api/univariate/selections", {"run_id": "r", "predicates": "bad"}),
        ("/api/univariate/selections", {"run_id": "r", "predicates": ["bad"]}),
        (
            "/api/multivariate/runs",
            {"selection_id": "s", "bivariate_run_id": "b", "objective": 3},
        ),
    )
    for path, payload in invalid_payloads:
        assert client.post(path, json=payload).status_code == 422
    assert client.get("/api/runs", params={"stage": "invalid"}).status_code == 422


@pytest.mark.parametrize(
    ("code", "expected"),
    [("analysis_not_found", 404), ("dependency_not_ready", 409), ("analysis_invalid", 422)],
)
def test_research_routes_redact_application_service_errors(code: str, expected: int) -> None:
    client = _route_client(RouteService(failure=code))
    responses = (
        client.post("/api/univariate/runs", json={"universe_id": "u"}),
        client.post("/api/univariate/selections", json={"run_id": "r"}),
        client.post("/api/bivariate/runs", json={"selection_id": "s"}),
        client.post(
            "/api/multivariate/runs",
            json={"selection_id": "s", "bivariate_run_id": "b"},
        ),
        client.get("/api/runs/r"),
        client.get("/api/runs", params={"stage": "univariate"}),
    )
    assert all(response.status_code == expected for response in responses)
    assert all(response.json()["detail"] == {"code": code} for response in responses)


FULL_WORKFLOW: dict[str, object] = {
    "workspace_id": "default",
    "metadata_universe": {
        "universe_id": "u1",
        "version": 1,
        "source_snapshot_id": "snap",
    },
    "univariate_selection": {
        "selection_id": "s1",
        "source_run_id": "ur1",
        "version": 1,
        "member_count": 2,
    },
    "stages": {
        "univariate": {
            "run_id": "ur1",
            "status": "succeeded",
            "input_ref": "u1",
            "input_snapshot_id": "snap",
        },
        "bivariate": {
            "run_id": "br1",
            "status": "succeeded",
            "input_ref": "s1",
            "input_snapshot_id": "snap",
        },
        "multivariate": {
            "run_id": "mr1",
            "status": "succeeded",
            "input_ref": "br1",
            "input_snapshot_id": "snap",
        },
    },
}


class CallbackStub:
    def __init__(self, *, fail_action: str | None = None, fail_refresh: bool = False) -> None:
        self.fail_action = fail_action
        self.fail_refresh = fail_refresh
        self.calls: list[tuple[str, dict[str, object]]] = []

    def workflow_state(self) -> dict[str, object]:
        if self.fail_refresh:
            raise RuntimeError("state unavailable")
        return FULL_WORKFLOW

    def _record(self, name: str, **values: object) -> None:
        self.calls.append((name, values))
        if self.fail_action == name:
            error = RuntimeError("internal detail")
            error.code = "typed_action_failure"  # type: ignore[attr-defined]
            raise error

    def create_metadata_universe(self, **filters: object) -> object:
        self._record("metadata", **filters)
        return object()

    def run_univariate(self, universe_id: str) -> dict[str, object]:
        self._record("univariate", universe_id=universe_id)
        return {}

    def create_univariate_selection(
        self, run_id: str, *, predicates: dict[str, object] | None = None
    ) -> object:
        self._record("selection", run_id=run_id, predicates=predicates)
        return object()

    def run_bivariate(self, selection_id: str) -> dict[str, object]:
        self._record("bivariate", selection_id=selection_id)
        return {}

    def run_multivariate(
        self,
        *,
        selection_id: str,
        bivariate_run_id: str,
        objective: str = "return_risk",
    ) -> dict[str, object]:
        self._record(
            "multivariate",
            selection_id=selection_id,
            bivariate_run_id=bivariate_run_id,
            objective=objective,
        )
        return {}


def test_execute_action_covers_all_commands_and_persisted_reconstruction() -> None:
    service = CallbackStub()
    persisted = persisted_browser_state(service)
    assert persisted.readiness == StageReadiness(True, True, True, True)

    state = BrowserState(
        universe_id="u1",
        univariate_run_id="ur1",
        selection_id="s1",
        bivariate_run_id="br1",
    )
    actions = (
        ("metadata-create-universe", {"filters": {"exchange": "XETRA"}}),
        ("univariate-compute", {}),
        ("univariate-save-selection", {}),
        ("bivariate-compute", {}),
        ("multivariate-optimize", {"objective": "minimum_risk"}),
        ("refresh", {}),
    )
    for action, kwargs in actions:
        result = execute_action(service, state, action=action, **kwargs)  # type: ignore[arg-type]
        assert result.readiness.multivariate

    assert service.calls[0] == ("metadata", {"exchange": "XETRA"})
    assert ("univariate", {"universe_id": "u1"}) in service.calls
    assert ("selection", {"run_id": "ur1", "predicates": None}) in service.calls
    assert ("bivariate", {"selection_id": "s1"}) in service.calls
    assert (
        "multivariate",
        {
            "selection_id": "s1",
            "bivariate_run_id": "br1",
            "objective": "minimum_risk",
        },
    ) in service.calls
    assert execute_action(service, state, action="unknown") is state


def test_execute_action_covers_not_ready_and_failure_recovery_paths() -> None:
    service = CallbackStub()
    empty = BrowserState()
    expected = {
        "univariate-compute": "metadata_not_ready",
        "univariate-save-selection": "univariate_not_ready",
        "bivariate-compute": "univariate_selection_not_ready",
        "multivariate-optimize": "bivariate_not_ready",
    }
    for action, code in expected.items():
        assert execute_action(service, empty, action=action).message_code == code

    partial = BrowserState(selection_id="s1")
    assert (
        execute_action(service, partial, action="multivariate-optimize").message_code
        == "bivariate_not_ready"
    )

    failing = CallbackStub(fail_action="univariate")
    result = execute_action(
        failing, BrowserState(universe_id="u1"), action="univariate-compute"
    )
    assert result.message_code == "typed_action_failure"
    assert result.universe_id == "u1"

    doubly_failing = CallbackStub(fail_action="univariate", fail_refresh=True)
    original = BrowserState(universe_id="u1")
    result = execute_action(doubly_failing, original, action="univariate-compute")
    assert result.universe_id == "u1"
    assert result.message_code == "typed_action_failure"


class UntypedCallbackFailure(CallbackStub):
    def run_univariate(self, universe_id: str) -> dict[str, object]:
        del universe_id
        raise RuntimeError("internal detail")


def test_execute_action_maps_untyped_failures_to_public_code() -> None:
    result = execute_action(
        UntypedCallbackFailure(),
        BrowserState(universe_id="u1"),
        action="univariate-compute",
    )
    assert result.message_code == "action_failed"


def test_hosted_api_shell_and_runtime_failures_are_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    import portfell.hosted_api as hosted_api

    client = TestClient(hosted_api.create_app())
    assert client.get("/healthz").json() == {"status": "ok"}

    monkeypatch.setattr(
        hosted_api,
        "load_app_database_config",
        lambda _path: (_ for _ in ()).throw(RuntimeError("secret dsn")),
    )
    with pytest.raises(hosted_api.HostedApiError, match="runtime_database_unavailable") as captured:
        hosted_api.create_runtime_app()
    assert "secret dsn" not in str(captured.value)


def test_hosted_api_runtime_preserves_typed_market_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import portfell.hosted_api as hosted_api
    from portfell.market_source.errors import MarketSourceError

    monkeypatch.setattr(
        hosted_api,
        "load_app_database_config",
        lambda _path: (_ for _ in ()).throw(MarketSourceError("market_source_config_missing")),
    )
    with pytest.raises(hosted_api.HostedApiError, match="market_source_config_missing"):
        hosted_api.create_runtime_app()
