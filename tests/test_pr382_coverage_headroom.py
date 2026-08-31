from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

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
        self.rows = rows

    def fetchone(self) -> Sequence[object] | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[Sequence[object]]:
        return list(self.rows)


class ScriptedConnection:
    def __init__(self, rows: list[list[Sequence[object]]], fail_at: int | None = None) -> None:
        self.rows = list(rows)
        self.fail_at = fail_at
        self.executed: list[tuple[str, Sequence[object] | None]] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, query: str, params: Sequence[object] | None = None) -> ScriptedCursor:
        self.executed.append((query, params))
        if self.fail_at == len(self.executed):
            raise RuntimeError("private database detail")
        rows = self.rows.pop(0) if self.rows else []
        return ScriptedCursor(rows)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def repo(
    rows: list[list[Sequence[object]]], fail_at: int | None = None
) -> tuple[PostgresAppStateRepository, ScriptedConnection]:
    connection = ScriptedConnection(rows, fail_at)
    return PostgresAppStateRepository(connection), connection


def assert_error(expected: str, call: object) -> None:
    assert isinstance(call, AppStateError)
    assert call.code == expected


def test_snapshot_paths() -> None:
    repository, connection = repo([[("snap-a", "fp-a", NOW, NOW)]])
    existing = repository.put_market_source_snapshot(
        snapshot_id="ignored", source_fingerprint="fp-a", observed_at=NOW
    )
    assert existing.snapshot_id == "snap-a"
    assert connection.commits == 0

    repository, connection = repo([[], [], [("snap-b", "fp-b", NOW, NOW)]])
    created = repository.put_market_source_snapshot(
        snapshot_id="snap-b", source_fingerprint="fp-b", observed_at=NOW
    )
    assert created.source_fingerprint == "fp-b"
    assert connection.commits == 1

    repository, _ = repo([[]])
    with pytest.raises(AppStateError) as captured:
        repository.get_market_source_snapshot("missing")
    assert_error(APP_STATE_NOT_FOUND, captured.value)

    repository, connection = repo([[], []], fail_at=2)
    with pytest.raises(AppStateError) as captured:
        repository.put_market_source_snapshot(
            snapshot_id="snap-c",
            source_fingerprint="fp-c",
            observed_at=NOW,
        )
    assert_error(APP_STATE_PERSISTENCE_FAILED, captured.value)
    assert connection.rollbacks == 1
    assert "private database detail" not in str(captured.value)


def test_universe_paths_and_member_validation() -> None:
    universe_row = ("u1", "s1", 2, "h1", NOW, NOW)
    repository, _ = repo([[universe_row], [("DE0001", "XETRA", "AAA")]])
    listed = repository.list_metadata_universes(limit=1)
    assert listed[0].members == (ListingIdentity("DE0001", "XETRA", "AAA"),)

    repository, _ = repo([[]])
    with pytest.raises(AppStateError) as captured:
        repository.get_metadata_universe("missing")
    assert_error(APP_STATE_NOT_FOUND, captured.value)

    for invalid in (0, 501):
        repository, _ = repo([])
        with pytest.raises(AppStateError) as captured:
            repository.list_metadata_universes(limit=invalid)
        assert_error(APP_STATE_CONFLICT, captured.value)

    member = ListingIdentity("DE0001", "XETRA", "AAA")
    for members in ((member, member), (ListingIdentity(" ", "XETRA", "AAA"),)):
        repository, _ = repo([[]])
        with pytest.raises(AppStateError) as captured:
            repository.create_metadata_universe(
                universe_id="invalid",
                source_snapshot_id="snap",
                version=1,
                content_hash="hash",
                members=members,
            )
        assert_error(APP_STATE_CONFLICT, captured.value)


def test_analysis_run_create_and_transition_paths() -> None:
    repository, connection = repo([])
    for stage, status in (
        ("wrong", "queued"),
        ("univariate", "succeeded"),
    ):
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
        assert_error(APP_STATE_INVALID_TRANSITION, captured.value)
    assert connection.executed == []

    repository, connection = repo([[('run-a',)], [RUN_ROW]])
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

    running = list(RUN_ROW)
    running[2] = "running"
    running[10] = None
    repository, connection = repo([[], [], [tuple(running)]])
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

    repository, connection = repo([[], []], fail_at=2)
    with pytest.raises(AppStateError) as captured:
        repository.create_analysis_run(
            run_id="run-f",
            stage="univariate",
            status="queued",
            input_snapshot_id="s",
            input_ref="u",
            logical_hash="h",
            algorithm_version="a",
        )
    assert_error(APP_STATE_PERSISTENCE_FAILED, captured.value)
    assert connection.rollbacks == 1

    invalid = (
        ("queued", None),
        ("unknown", None),
        ("failed", None),
        ("succeeded", "unexpected"),
    )
    for status, failure in invalid:
        repository, _ = repo([])
        with pytest.raises(AppStateError) as captured:
            repository.transition_analysis_run(
                run_id="run-a",
                status=status,
                failure_code=failure,
            )
        assert_error(APP_STATE_INVALID_TRANSITION, captured.value)

    repository, connection = repo([[], [tuple(running)]])
    transitioned = repository.transition_analysis_run(
        run_id="run-a", status="running"
    )
    assert transitioned.status == "running"
    assert connection.commits == 1

    failed = list(RUN_ROW)
    failed[2] = "failed"
    failed[7] = "calculation_failed"
    repository, connection = repo([[], [tuple(failed)]])
    transitioned = repository.transition_analysis_run(
        run_id="run-a",
        status="failed",
        failure_code="calculation_failed",
    )
    assert transitioned.failure_code == "calculation_failed"
    assert connection.commits == 1

    repository, connection = repo([[]], fail_at=1)
    with pytest.raises(AppStateError) as captured:
        repository.transition_analysis_run(run_id="run-a", status="succeeded")
    assert_error(APP_STATE_INVALID_TRANSITION, captured.value)
    assert connection.rollbacks == 1


def test_analysis_run_read_paths() -> None:
    repository, _ = repo([[]])
    with pytest.raises(AppStateError) as captured:
        repository.get_analysis_run("missing")
    assert_error(APP_STATE_NOT_FOUND, captured.value)

    repository, _ = repo([[RUN_ROW]])
    assert repository.list_analysis_runs(limit=1)[0].logical_hash == "logical-a"

    repository, _ = repo([[RUN_ROW]])
    assert repository.list_analysis_runs(stage="univariate", limit=1)[0].stage == "univariate"

    repository, _ = repo([])
    with pytest.raises(AppStateError) as captured:
        repository.list_analysis_runs(stage="invalid")
    assert_error(APP_STATE_NOT_FOUND, captured.value)


def test_artifact_paths() -> None:
    repository, connection = repo([[], [], [ARTIFACT_ROW]])
    created = repository.put_analysis_artifact(
        artifact_id="artifact-a",
        run_id="run-a",
        artifact_type="summary",
        content_hash="hash-a",
        document={"value": 1},
    )
    assert created.document == {"value": 1}
    assert connection.commits == 1

    repository, _ = repo([[ARTIFACT_ROW]])
    assert repository.list_analysis_artifacts("run-a")[0].artifact_id == "artifact-a"

    repository, connection = repo([[], []], fail_at=2)
    with pytest.raises(AppStateError) as captured:
        repository.put_analysis_artifact(
            artifact_id="artifact-b",
            run_id="run-a",
            artifact_type="rows",
            content_hash="hash-b",
            document={"value": 2},
        )
    assert_error(APP_STATE_PERSISTENCE_FAILED, captured.value)
    assert connection.rollbacks == 1

    repository, _ = repo([[('a', 'r', 't', 'h', [1, 2], NOW)]])
    with pytest.raises(AppStateError) as captured:
        repository.list_analysis_artifacts("r")
    assert_error(APP_STATE_PERSISTENCE_FAILED, captured.value)


def test_selection_paths() -> None:
    selection = ("sel-a", "run-a", 2, "hash-s", NOW, NOW)
    member = ("DE0001", "XETRA", "AAA")
    identity = ListingIdentity(*member)

    repository, connection = repo([[('sel-a',)], [selection], [member]])
    existing = repository.create_univariate_selection(
        selection_id="ignored",
        source_run_id="run-a",
        version=9,
        content_hash="hash-s",
        members=(identity,),
    )
    assert existing.selection_id == "sel-a"
    assert connection.commits == 0

    repository, connection = repo([[], [], [], [selection], [member]])
    created = repository.create_univariate_selection(
        selection_id="sel-a",
        source_run_id="run-a",
        version=2,
        content_hash="hash-s",
        members=(identity,),
    )
    assert created.members == (identity,)
    assert connection.commits == 1

    repository, _ = repo([[selection], [member]])
    assert repository.list_univariate_selections(limit=1)[0].version == 2

    repository, _ = repo([[]])
    with pytest.raises(AppStateError) as captured:
        repository.get_univariate_selection("missing")
    assert_error(APP_STATE_NOT_FOUND, captured.value)


def put_decision(repository: PostgresAppStateRepository, winner: str = "candidate-a") -> object:
    return repository.put_decision_artifact(
        decision_id="decision-a",
        run_id="run-m",
        objective="return_risk",
        winning_candidate_id=winner,
        requested_method="Mean Variance",
        actual_method="Mean Variance",
        available=True,
        production_eligible=True,
        reason=None,
        document={"score": 1},
    )


def test_decision_paths() -> None:
    repository, _ = repo([])
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
    assert_error(APP_STATE_CONFLICT, captured.value)

    repository, connection = repo([[DECISION_ROW]])
    existing = put_decision(repository)
    assert getattr(existing, "decision_id") == "decision-a"
    assert connection.commits == 0

    repository, _ = repo([[DECISION_ROW]])
    with pytest.raises(AppStateError) as captured:
        put_decision(repository, "candidate-b")
    assert_error(APP_STATE_CONFLICT, captured.value)

    repository, connection = repo([[], [], [DECISION_ROW]])
    created = put_decision(repository)
    assert getattr(created, "winning_candidate_id") == "candidate-a"
    assert connection.commits == 1

    repository, connection = repo([[], []], fail_at=2)
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
    assert_error(APP_STATE_PERSISTENCE_FAILED, captured.value)
    assert connection.rollbacks == 1

    repository, _ = repo([[]])
    with pytest.raises(AppStateError) as captured:
        repository.get_decision_artifact("missing")
    assert_error(APP_STATE_NOT_FOUND, captured.value)


def test_ui_preference_paths() -> None:
    repository, connection = repo([[], [("objective", '"return_risk"', NOW)]])
    record = repository.set_ui_preference("objective", "return_risk")
    assert record.value == "return_risk"
    assert connection.commits == 1

    repository, _ = repo([[]])
    assert repository.get_ui_preference("missing") is None

    repository, _ = repo([[('a', '1', NOW), ('b', '{"x":2}', NOW)]])
    assert [item.value for item in repository.list_ui_preferences()] == [1, {"x": 2}]

    repository, connection = repo([[]], fail_at=1)
    with pytest.raises(AppStateError) as captured:
        repository.set_ui_preference("x", True)
    assert_error(APP_STATE_PERSISTENCE_FAILED, captured.value)
    assert connection.rollbacks == 1

    repository, _ = repo([[], []])
    with pytest.raises(AppStateError) as captured:
        repository.set_ui_preference("vanishing", None)
    assert_error(APP_STATE_NOT_FOUND, captured.value)


class RouteService:
    def __init__(self, failure: str | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[str, dict[str, object]]] = []

    def fail(self) -> None:
        if self.failure:
            raise ApplicationServiceError(self.failure)

    def run_univariate(self, universe_id: str) -> dict[str, object]:
        self.fail()
        self.calls.append(("univariate", {"universe_id": universe_id}))
        return {"run_id": "uni-run", "status": "succeeded"}

    def create_univariate_selection(
        self,
        run_id: str,
        *,
        predicates: list[dict[str, object]] | None = None,
    ) -> UnivariateSelectionRecord:
        self.fail()
        self.calls.append(("selection", {"run_id": run_id, "predicates": predicates}))
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
        self.fail()
        self.calls.append(("bivariate", {"selection_id": selection_id}))
        return {"run_id": "bi-run", "status": "succeeded"}

    def run_multivariate(
        self,
        *,
        selection_id: str,
        bivariate_run_id: str,
        objective: str = "return_risk",
    ) -> dict[str, object]:
        self.fail()
        self.calls.append(
            (
                "multivariate",
                {
                    "selection_id": selection_id,
                    "bivariate_run_id": bivariate_run_id,
                    "objective": objective,
                },
            )
        )
        return {"run_id": "multi-run", "status": "succeeded"}

    def run_detail(self, run_id: str) -> dict[str, object]:
        self.fail()
        self.calls.append(("detail", {"run_id": run_id}))
        return {"run_id": run_id}

    def stage_history(
        self,
        stage: str,
        *,
        limit: int = 100,
    ) -> tuple[dict[str, object], ...]:
        self.fail()
        self.calls.append(("history", {"stage": stage, "limit": limit}))
        return ({"run_id": "history-run", "stage": stage},)


def client_for(service: RouteService) -> TestClient:
    app = FastAPI()
    app.include_router(research_router(service))
    return TestClient(app)


def test_research_routes_success_and_defaults() -> None:
    service = RouteService()
    client = client_for(service)
    response = client.post("/api/univariate/runs", json={"universe_id": "u1"})
    assert response.json()["run_id"] == "uni-run"

    selection = client.post(
        "/api/univariate/selections",
        json={
            "run_id": "uni-run",
            "predicates": [{"metric": "sharpe_ratio", "min": 1.0}],
        },
    )
    assert selection.json()["members"] == [
        {"isin": "DE0001", "exchange": "XETRA", "code": "AAA"}
    ]

    assert client.post(
        "/api/bivariate/runs",
        json={"selection_id": "selection-a"},
    ).status_code == 200
    assert client.post(
        "/api/multivariate/runs",
        json={"selection_id": "selection-a", "bivariate_run_id": "bi-run"},
    ).status_code == 200
    assert service.calls[-1][1]["objective"] == "return_risk"

    assert client.get("/api/runs/multi-run").json() == {"run_id": "multi-run"}
    history = client.get("/api/runs", params={"stage": "univariate", "limit": 7})
    assert history.json()["total"] == 1
    assert service.calls[-1][1]["limit"] == 7

    assert client.post(
        "/api/univariate/selections",
        json={"run_id": "uni-run"},
    ).status_code == 200
    assert service.calls[-1][1]["predicates"] is None


def test_research_routes_validation() -> None:
    client = client_for(RouteService())
    invalid = (
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
    for path, payload in invalid:
        assert client.post(path, json=payload).status_code == 422
    assert client.get("/api/runs", params={"stage": "invalid"}).status_code == 422


@pytest.mark.parametrize(
    ("code", "status"),
    (
        ("analysis_not_found", 404),
        ("dependency_not_ready", 409),
        ("analysis_invalid", 422),
    ),
)
def test_research_routes_redact_service_failures(code: str, status: int) -> None:
    client = client_for(RouteService(code))
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
    assert all(response.status_code == status for response in responses)
    assert all(response.json()["detail"] == {"code": code} for response in responses)


WORKFLOW: dict[str, object] = {
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
    def __init__(self, fail_action: str | None = None, fail_refresh: bool = False) -> None:
        self.fail_action = fail_action
        self.fail_refresh = fail_refresh
        self.calls: list[tuple[str, dict[str, object]]] = []

    def workflow_state(self) -> dict[str, object]:
        if self.fail_refresh:
            raise RuntimeError("state unavailable")
        return WORKFLOW

    def record(self, name: str, **values: object) -> None:
        self.calls.append((name, values))
        if self.fail_action == name:
            error = RuntimeError("internal detail")
            setattr(error, "code", "typed_action_failure")
            raise error

    def create_metadata_universe(self, **filters: object) -> object:
        self.record("metadata", **filters)
        return object()

    def run_univariate(self, universe_id: str) -> dict[str, object]:
        self.record("univariate", universe_id=universe_id)
        return {}

    def create_univariate_selection(
        self,
        run_id: str,
        *,
        predicates: dict[str, object] | None = None,
    ) -> object:
        self.record("selection", run_id=run_id, predicates=predicates)
        return object()

    def run_bivariate(self, selection_id: str) -> dict[str, object]:
        self.record("bivariate", selection_id=selection_id)
        return {}

    def run_multivariate(
        self,
        *,
        selection_id: str,
        bivariate_run_id: str,
        objective: str = "return_risk",
    ) -> dict[str, object]:
        self.record(
            "multivariate",
            selection_id=selection_id,
            bivariate_run_id=bivariate_run_id,
            objective=objective,
        )
        return {}


def test_execute_action_success_paths() -> None:
    service = CallbackStub()
    assert persisted_browser_state(service).readiness == StageReadiness(True, True, True, True)
    state = BrowserState(
        universe_id="u1",
        univariate_run_id="ur1",
        selection_id="s1",
        bivariate_run_id="br1",
    )
    commands = (
        ("metadata-create-universe", {"filters": {"exchange": "XETRA"}}),
        ("univariate-compute", {}),
        ("univariate-save-selection", {}),
        ("bivariate-compute", {}),
        ("multivariate-optimize", {"objective": "minimum_risk"}),
        ("refresh", {}),
    )
    for action, kwargs in commands:
        result = execute_action(service, state, action=action, **kwargs)  # type: ignore[arg-type]
        assert result.readiness.multivariate
    assert execute_action(service, state, action="unknown") is state
    assert service.calls[0] == ("metadata", {"exchange": "XETRA"})


def test_execute_action_not_ready_and_failure_paths() -> None:
    service = CallbackStub()
    expected = {
        "univariate-compute": "metadata_not_ready",
        "univariate-save-selection": "univariate_not_ready",
        "bivariate-compute": "univariate_selection_not_ready",
        "multivariate-optimize": "bivariate_not_ready",
    }
    for action, code in expected.items():
        assert execute_action(service, BrowserState(), action=action).message_code == code

    partial = BrowserState(selection_id="s1")
    result = execute_action(service, partial, action="multivariate-optimize")
    assert result.message_code == "bivariate_not_ready"

    failing = CallbackStub(fail_action="univariate")
    result = execute_action(
        failing,
        BrowserState(universe_id="u1"),
        action="univariate-compute",
    )
    assert result.message_code == "typed_action_failure"
    assert result.universe_id == "u1"

    double = CallbackStub(fail_action="univariate", fail_refresh=True)
    result = execute_action(
        double,
        BrowserState(universe_id="u1"),
        action="univariate-compute",
    )
    assert result.message_code == "typed_action_failure"
    assert result.universe_id == "u1"


class UntypedFailure(CallbackStub):
    def run_univariate(self, universe_id: str) -> dict[str, object]:
        del universe_id
        raise RuntimeError("private detail")


def test_execute_action_untyped_failure() -> None:
    result = execute_action(
        UntypedFailure(),
        BrowserState(universe_id="u1"),
        action="univariate-compute",
    )
    assert result.message_code == "action_failed"


def test_hosted_api_shell_and_redacted_runtime_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import portfell.hosted_api as hosted_api

    client = TestClient(hosted_api.create_app())
    assert client.get("/healthz").json() == {"status": "ok"}
    monkeypatch.setattr(
        hosted_api,
        "load_app_database_config",
        lambda _path: (_ for _ in ()).throw(RuntimeError("secret dsn")),
    )
    with pytest.raises(hosted_api.HostedApiError) as captured:
        hosted_api.create_runtime_app()
    assert str(captured.value) == "runtime_database_unavailable"


def test_hosted_api_preserves_typed_market_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import portfell.hosted_api as hosted_api
    from portfell.market_source.errors import MarketSourceError

    monkeypatch.setattr(
        hosted_api,
        "load_app_database_config",
        lambda _path: (_ for _ in ()).throw(
            MarketSourceError("market_source_config_missing")
        ),
    )
    with pytest.raises(hosted_api.HostedApiError) as captured:
        hosted_api.create_runtime_app()
    assert str(captured.value) == "market_source_config_missing"
