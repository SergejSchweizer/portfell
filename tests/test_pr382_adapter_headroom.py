from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from portfell.app_services.research import ApplicationServiceError
from portfell.app_state.contracts import ListingIdentity, UnivariateSelectionRecord
from portfell.dash_app.callbacks import execute_action, persisted_browser_state
from portfell.dash_app.state import BrowserState, StageReadiness
from portfell.modules.bivariate import bivariate_router
from portfell.modules.multivariate import multivariate_router
from portfell.modules.univariate import univariate_router

NOW = datetime(2026, 8, 31, 20, 0, tzinfo=UTC)


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
    application = FastAPI()
    application.include_router(univariate_router(service))
    application.include_router(bivariate_router(service))
    application.include_router(multivariate_router(service))
    return TestClient(application)


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
    assert selection.json()["members"] == [{"isin": "DE0001", "exchange": "XETRA", "code": "AAA"}]

    response = client.post(
        "/api/bivariate/runs",
        json={"selection_id": "selection-a"},
    )
    assert response.status_code == 200

    response = client.post(
        "/api/multivariate/runs",
        json={"selection_id": "selection-a", "bivariate_run_id": "bi-run"},
    )
    assert response.status_code == 200
    assert service.calls[-1][1]["objective"] == "return_risk"

    assert client.get("/api/multivariate/runs/multi-run").json() == {"run_id": "multi-run"}
    history = client.get("/api/univariate/runs", params={"limit": 7})
    assert history.json()["total"] == 1
    assert service.calls[-1][1]["limit"] == 7

    response = client.post(
        "/api/univariate/selections",
        json={"run_id": "uni-run"},
    )
    assert response.status_code == 200
    assert service.calls[-1][1]["predicates"] is None


def test_research_routes_validate_payload_shape() -> None:
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
    assert client.get("/api/univariate/runs", params={"limit": 0}).status_code == 422


@pytest.mark.parametrize(
    ("error_code", "status"),
    (
        ("analysis_not_found", 404),
        ("dependency_not_ready", 409),
        ("analysis_invalid", 422),
    ),
)
def test_research_routes_redact_service_failures(error_code: str, status: int) -> None:
    client = client_for(RouteService(error_code))
    responses = (
        client.post("/api/univariate/runs", json={"universe_id": "u"}),
        client.post("/api/univariate/selections", json={"run_id": "r"}),
        client.post("/api/bivariate/runs", json={"selection_id": "s"}),
        client.post(
            "/api/multivariate/runs",
            json={"selection_id": "s", "bivariate_run_id": "b"},
        ),
        client.get("/api/univariate/runs/r"),
        client.get("/api/univariate/runs"),
    )
    assert all(response.status_code == status for response in responses)
    expected = {"code": error_code}
    assert all(response.json()["detail"] == expected for response in responses)


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


class ActionFailure(RuntimeError):
    def __init__(self, error_code: str) -> None:
        self.code = error_code
        super().__init__(error_code)


class CallbackService:
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
            raise ActionFailure("typed_action_failure")

    def create_universe_and_start_univariate(self, **filters: object) -> object:
        self.record("metadata", **filters)
        return object()

    def create_univariate_selection(
        self,
        run_id: str,
        *,
        predicates: Mapping[str, object] | None = None,
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
    service = CallbackService()
    persisted = persisted_browser_state(service)
    assert persisted.readiness == StageReadiness(True, True, True, True)

    state = BrowserState(
        universe_id="u1",
        univariate_run_id="ur1",
        selection_id="s1",
        bivariate_run_id="br1",
    )
    commands = (
        ("metadata-create-universe", {"filters": {"exchange": "XETRA"}}),
        ("univariate-save-selection", {}),
        ("bivariate-compute", {}),
        ("multivariate-optimize", {"objective": "minimum_risk"}),
        ("refresh", {}),
    )
    for action, kwargs in commands:
        result = execute_action(
            service,
            state,
            action=action,
            **kwargs,  # type: ignore[arg-type]
        )
        assert result.readiness.multivariate
    assert execute_action(service, state, action="unknown") is state
    assert service.calls[0] == ("metadata", {"exchange": "XETRA"})


def test_execute_action_not_ready_and_failure_recovery() -> None:
    service = CallbackService()
    expected = {
        "univariate-save-selection": "univariate_not_ready",
        "bivariate-compute": "univariate_selection_not_ready",
        "multivariate-optimize": "bivariate_not_ready",
    }
    for action, message_code in expected.items():
        result = execute_action(service, BrowserState(), action=action)
        assert result.message_code == message_code

    partial = BrowserState(selection_id="s1")
    result = execute_action(service, partial, action="multivariate-optimize")
    assert result.message_code == "bivariate_not_ready"

    failing = CallbackService(fail_action="metadata")
    result = execute_action(
        failing,
        BrowserState(),
        action="metadata-create-universe",
    )
    assert result.message_code == "typed_action_failure"
    assert result.universe_id == "u1"

    double = CallbackService(fail_action="metadata", fail_refresh=True)
    result = execute_action(
        double,
        BrowserState(),
        action="metadata-create-universe",
    )
    assert result.message_code == "typed_action_failure"
    assert result.universe_id is None


class UntypedFailure(CallbackService):
    def create_universe_and_start_univariate(self, **filters: object) -> object:
        del filters
        raise RuntimeError("private detail")


def test_execute_action_maps_untyped_failure() -> None:
    result = execute_action(
        UntypedFailure(),
        BrowserState(),
        action="metadata-create-universe",
    )
    assert result.message_code == "action_failed"


def test_hosted_api_shell_and_redacted_runtime_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import portfell.hosted_api as hosted_api

    client = TestClient(hosted_api.create_app())
    assert client.get("/healthz").json() == {"status": "ok"}

    def fail_config(_path: object) -> object:
        raise RuntimeError("secret dsn")

    monkeypatch.setattr(hosted_api, "load_app_database_config", fail_config)
    with pytest.raises(hosted_api.HostedApiError) as error:
        hosted_api.create_runtime_app()
    assert str(error.value) == "runtime_database_unavailable"


def test_hosted_api_preserves_typed_market_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import portfell.hosted_api as hosted_api
    from portfell.market_source.errors import MarketSourceError

    def fail_config(_path: object) -> object:
        raise MarketSourceError("market_source_config_missing")

    monkeypatch.setattr(hosted_api, "load_app_database_config", fail_config)
    with pytest.raises(hosted_api.HostedApiError) as error:
        hosted_api.create_runtime_app()
    assert str(error.value) == "market_source_config_missing"
