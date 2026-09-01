from __future__ import annotations

from portfell.dash_app.callbacks import execute_action
from portfell.dash_app.state import BrowserState, browser_state_from_workflow


def _workflow(
    *,
    universe_id: str = "u1",
    univariate_input: str = "u1",
    selection_source: str = "run-u",
    bivariate_input: str = "s1",
    multivariate_input: str = "run-b",
) -> dict[str, object]:
    return {
        "workspace_id": "default",
        "metadata_universe": {
            "universe_id": universe_id,
            "version": 3,
            "source_snapshot_id": "snapshot-metadata",
            "member_count": 4,
        },
        "univariate_selection": {
            "selection_id": "s1",
            "source_run_id": selection_source,
            "version": 2,
            "member_count": 3,
        },
        "stages": {
            "univariate": {
                "run_id": "run-u",
                "status": "succeeded",
                "input_ref": univariate_input,
                "input_snapshot_id": "snapshot-u",
            },
            "bivariate": {
                "run_id": "run-b",
                "status": "succeeded",
                "input_ref": bivariate_input,
                "input_snapshot_id": "snapshot-b",
            },
            "multivariate": {
                "run_id": "run-m",
                "status": "succeeded",
                "input_ref": multivariate_input,
                "input_snapshot_id": "snapshot-m",
            },
        },
    }


def test_readiness_is_dependency_exact_not_status_only() -> None:
    state = browser_state_from_workflow(_workflow())
    assert state.readiness.metadata is True
    assert state.readiness.univariate is True
    assert state.readiness.bivariate is True
    assert state.readiness.multivariate is True

    changed_universe = browser_state_from_workflow(_workflow(universe_id="u2"))
    assert changed_universe.readiness.metadata is True
    assert changed_universe.readiness.univariate is False
    assert changed_universe.readiness.bivariate is False
    assert changed_universe.readiness.multivariate is False

    changed_selection = browser_state_from_workflow(_workflow(selection_source="old-run"))
    assert changed_selection.readiness.univariate is False
    assert changed_selection.readiness.bivariate is False
    assert changed_selection.readiness.multivariate is False

    changed_bivariate = browser_state_from_workflow(_workflow(bivariate_input="old-selection"))
    assert changed_bivariate.readiness.univariate is True
    assert changed_bivariate.readiness.bivariate is False
    assert changed_bivariate.readiness.multivariate is False

    changed_multivariate = browser_state_from_workflow(
        _workflow(multivariate_input="old-bivariate")
    )
    assert changed_multivariate.readiness.bivariate is True
    assert changed_multivariate.readiness.multivariate is False


def test_store_contains_identifiers_and_presentation_state_only() -> None:
    store = browser_state_from_workflow(_workflow()).to_store()
    serialized = repr(store).lower()
    for forbidden in ("quotes", "covariance", "weights", "password", "database_url", "artifacts"):
        assert forbidden not in serialized
    restored = BrowserState.from_store(store)
    assert restored.universe_id == "u1"
    assert restored.selection_id == "s1"
    assert restored.multivariate_run_id == "run-m"


class Service:
    def __init__(self) -> None:
        self.workflow = _workflow()
        self.calls: list[tuple[str, object]] = []

    def workflow_state(self) -> dict[str, object]:
        return self.workflow

    def create_universe_and_start_univariate(self, **filters: object) -> object:
        self.calls.append(("metadata", filters))
        return object()

    def create_univariate_selection(self, run_id: str, *, predicates=None) -> object:
        self.calls.append(("selection", (run_id, predicates)))
        return object()

    def run_bivariate(self, selection_id: str) -> dict[str, object]:
        self.calls.append(("bivariate", selection_id))
        return {"run_id": "run-b"}

    def run_multivariate(
        self, *, selection_id: str, bivariate_run_id: str, objective: str = "return_risk"
    ) -> dict[str, object]:
        self.calls.append(("multivariate", (selection_id, bivariate_run_id, objective)))
        return {"run_id": "run-m"}


def test_explicit_actions_delegate_using_persisted_ids() -> None:
    service = Service()
    state = browser_state_from_workflow(service.workflow_state())
    execute_action(service, state, action="metadata-create-universe")
    execute_action(service, state, action="univariate-save-selection")
    execute_action(service, state, action="bivariate-compute")
    execute_action(service, state, action="multivariate-optimize", objective="minimum_risk")
    assert service.calls == [
        ("metadata", {}),
        ("selection", ("run-u", None)),
        ("bivariate", "s1"),
        ("multivariate", ("s1", "run-b", "minimum_risk")),
    ]


def test_route_refresh_is_read_only() -> None:
    service = Service()
    execute_action(service, BrowserState(), action="refresh")
    assert service.calls == []


def test_revision_state_keeps_previous_run_separate_from_current() -> None:
    workflow = _workflow()
    workflow["history"] = {
        "univariate": [
            {"run_id": "run-u-new", "status": "running", "input_ref": "u1"},
            {"run_id": "run-u-old", "status": "succeeded", "input_ref": "u0"},
        ],
        "bivariate": [{"run_id": "run-b-old", "status": "succeeded", "input_ref": "old-selection"}],
        "multivariate": [],
    }
    state = browser_state_from_workflow(workflow)
    assert state.current_input_revision == "universe:u1|selection:s1"
    assert state.current_ready_runs is None or "univariate" not in state.current_ready_runs
    assert state.previous_ready_runs == {
        "univariate": "run-u-old",
        "bivariate": "run-b-old",
    }
    assert state.previous_ready_run == "run-b-old"


def test_revision_state_switches_atomically_on_matching_success() -> None:
    workflow = _workflow()
    workflow["history"] = {
        "univariate": [{"run_id": "run-u", "status": "succeeded", "input_ref": "u1"}],
        "bivariate": [{"run_id": "run-b", "status": "succeeded", "input_ref": "s1"}],
        "multivariate": [{"run_id": "run-m", "status": "succeeded", "input_ref": "run-b"}],
    }
    state = browser_state_from_workflow(workflow)
    assert state.current_ready_runs == {
        "univariate": "run-u",
        "bivariate": "run-b",
        "multivariate": "run-m",
    }
    assert state.current_ready_run == "run-m"
    assert state.previous_ready_run is None
