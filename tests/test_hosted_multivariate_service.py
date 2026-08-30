from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from portfell.hosted_api_service_support import stable_hash
from portfell.hosted_api_state import HostedApiState, ProjectRecord, SelectionRecord
from portfell.hosted_local_project_repository import LocalProjectRepository
from portfell.hosted_local_selection_repository import LocalSelectionRepository
from portfell.hosted_multivariate_run_repository import LocalMultivariateRunRepository
from portfell.hosted_multivariate_service import MultivariateResearchService
from portfell.hosted_repository_importer import (
    InMemoryProjectRepository,
    TenantProject,
    TenantSelection,
)
from portfell.hosted_research_repository import HostedResearchRepository
from portfell.hosted_research_workflow import (
    ResearchRun,
    UnivariateSelection,
    bivariate_source_id,
    univariate_source_id,
)
from portfell.hosted_selection_repository import InMemorySelectionRepository
from portfell.hosted_workspace import LocalWorkspaceStore
from portfell.hosted_workspace_repository import persist_local_workspace, restore_local_workspace
from portfell.income import INCOME_CONTRACT
from portfell.table_io import JsonRow


@dataclass
class _Data:
    quotes: tuple[JsonRow, ...]
    dividends: tuple[JsonRow, ...]

    def selected_rows(self, member_ids: tuple[str, ...], *, dataset: str) -> tuple[JsonRow, ...]:
        del member_ids
        return self.quotes if dataset == "quotes" else self.dividends

    def has_selected_rows(self, member_ids: tuple[str, ...], *, dataset: str) -> bool:
        return bool(self.selected_rows(member_ids, dataset=dataset))

    def build_univariate_rows(
        self,
        member_ids: tuple[str, ...],
        *,
        on_progress: Callable[[int], None] | None = None,
    ) -> tuple[JsonRow, ...]:
        del member_ids, on_progress
        return ()


@dataclass
class _Persistence:
    persisted: int = 0

    def persist(self) -> None:
        self.persisted += 1


def _service(
    state: HostedApiState,
    data: _Data,
    persistence: _Persistence,
    worker_count: Callable[[], int | None] | None = None,
) -> MultivariateResearchService:
    return MultivariateResearchService(
        data,
        persistence,
        HostedResearchRepository(state),
        LocalProjectRepository(state),
        LocalSelectionRepository(state),
        LocalMultivariateRunRepository(state),
        lambda: state.all_isins_rows,
        worker_count or (lambda: 1),
        None,
    )


def _fixtures() -> tuple[HostedApiState, _Data, str, str]:
    user_id, project_id, univariate_run_id = "user-a", "project-a", "univariate-a"
    keys = [(f"IE{index}", "X", f"ETF{index}") for index in range(5)]
    rows = tuple(
        {
            "isin": isin,
            "exchange": exchange,
            "code": code,
            "distribution_frequency": "monthly",
            "quote_history_production_eligible": True,
        }
        for isin, exchange, code in keys
    )
    selection = UnivariateSelection(
        selection_id="univariate-selection-a",
        user_id=user_id,
        source_run_id=univariate_run_id,
        member_ids=tuple(f"{isin}:{exchange}:{code}" for isin, exchange, code in keys),
        predicates=(),
        rows=rows,
        input_count=5,
    )
    state = HostedApiState(
        projects_by_id={project_id: ProjectRecord(project_id, user_id, "A")},
        selections_by_id={
            "metadata-selection-a": SelectionRecord(
                "metadata-selection-a",
                user_id,
                project_id,
                "A",
                selection.member_ids,
            )
        },
        all_isins_rows=tuple(
            {"isin": isin, "exchange": exchange, "code": code, "instrument_type": "ETF"}
            for isin, exchange, code in keys
        ),
        univariate_runs_by_id={
            univariate_run_id: ResearchRun(
                univariate_run_id,
                user_id,
                univariate_source_id("metadata-selection-a", "shared-market"),
                "complete",
                rows,
                5,
                5,
            )
        },
        univariate_selections_by_id={selection.selection_id: selection},
        quote_run_by_univariate_run_id={univariate_run_id: "quote-a"},
    )
    bivariate_run_id = "bivariate-a"
    state.bivariate_runs_by_id[bivariate_run_id] = ResearchRun(
        bivariate_run_id, user_id, bivariate_source_id(selection), "complete", (), 10, 10
    )
    start = date(2023, 1, 1)
    quotes = tuple(
        {
            "isin": isin,
            "exchange": exchange,
            "code": code,
            "date": (start + timedelta(days=day)).isoformat(),
            "adjusted_close": 100 + index * 5 + day * (0.03 + index * 0.001),
        }
        for index, (isin, exchange, code) in enumerate(keys)
        for day in range(505)
    )
    dividends = tuple(
        {
            "isin": isin,
            "exchange": exchange,
            "code": code,
            "event_id": f"{code}-{month}",
            "payment_date": f"2024-{month:02d}-01",
            "amount": 0.2 + index * 0.01,
            "currency": "EUR",
        }
        for index, (isin, exchange, code) in enumerate(keys)
        for month in range(1, 13)
    )
    return state, _Data(quotes, dividends), project_id, bivariate_run_id


def test_multivariate_service_resolves_pinned_project_dependencies_and_persists_result() -> None:
    state, data, project_id, bivariate_run_id = _fixtures()
    persistence = _Persistence()
    service = _service(state, data, persistence)

    plan = service.plan("user-a", project_id, bivariate_run_id, {})
    assert plan["allowed"] is True
    assert plan["listing_count"] == 5
    assert plan["phases"][-1] == "validate_candidates"

    started = service.start("user-a", project_id, bivariate_run_id, {})
    assert started["status"] == "running"
    assert started["estimated_remaining_seconds"] is not None
    service._advance("user-a", str(started["run_id"]), "build_risk_model", 2)  # pyright: ignore[reportPrivateUsage]
    service._advance("user-a", str(started["run_id"]), "resolve_inputs", 1)  # pyright: ignore[reportPrivateUsage]
    running = service.status("user-a", str(started["run_id"]))
    assert running["phase"] == "build_risk_model"
    assert running["completed_units"] == 2
    service.complete("user-a", str(started["run_id"]))
    status = service.status("user-a", str(started["run_id"]))

    assert status["status"] == "complete"
    assert status["estimated_remaining_seconds"] == 0
    assert status["input_snapshot_id"]
    assert service.summary("user-a", str(started["run_id"]))["candidate_etf_count"] == 5
    candidates = service.candidates("user-a", str(started["run_id"]))["items"]
    assert len(candidates) == 7
    assert "highest_monthly_return" in {candidate["method"] for candidate in candidates}
    assert all(candidate["var"] is not None for candidate in candidates)
    assert all(candidate["maximum_weight"] is not None for candidate in candidates)
    assert all(candidate["herfindahl_index"] is not None for candidate in candidates)
    assert all(candidate["effective_holding_count"] is not None for candidate in candidates)
    candidate_id = str(candidates[0]["candidate_id"])
    detail = service.candidate_detail("user-a", str(started["run_id"]), candidate_id)
    assert detail["candidate_id"] == candidate_id
    assert "total_return" in detail
    assert "average_monthly_return" in detail
    assert "average_annual_return" in detail
    assert "max_drawdown" in detail
    assert service.risk_contributions("user-a", str(started["run_id"]), candidate_id)["items"]
    assert service.income_evidence("user-a", str(started["run_id"]))["items"]
    artifacts = service.artifacts("user-a", str(started["run_id"]))
    assert artifacts["input_snapshot"]["metadata_selection_id"] == "metadata-selection-a"
    assert artifacts["input_snapshot"]["univariate_selection_id"] == "univariate-selection-a"
    assert len(artifacts["input_snapshot"]["quote_artifact_ids"]) == 5
    assert len(artifacts["input_snapshot"]["dividend_artifact_ids"]) == 5
    assert artifacts["risk_model"]["estimator"] == "ledoit_wolf"
    assert artifacts["structure"]["risk_model_id"] == artifacts["risk_model"]["risk_model_id"]
    assert len(artifacts["income_distribution_events"]) == 60
    assert len(artifacts["income_monthly_distributions"]) == 60
    assert len(artifacts["income_metrics"]) == 5
    assert all("policy_version" in row for row in artifacts["income_warnings"])
    components = service.components("user-a", str(started["run_id"]), limit=3, offset=0)
    assert components["total"] == 25
    assert len(components["items"]) == 3
    assert state.current_multivariate_run_by_project[project_id] == started["run_id"]
    assert persistence.persisted >= 1


def test_multivariate_service_completes_a_mixed_distribution_frequency_portfolio() -> None:
    state, data, project_id, bivariate_run_id = _fixtures()
    selection = state.univariate_selections_by_id["univariate-selection-a"]
    frequencies = ("monthly", "quarterly", "semiannual", "monthly", "quarterly")
    state.univariate_selections_by_id[selection.selection_id] = replace(
        selection,
        rows=tuple(
            {**row, "distribution_frequency": frequency}
            for row, frequency in zip(selection.rows, frequencies, strict=True)
        ),
    )
    service = _service(state, data, _Persistence())

    started = service.start("user-a", project_id, bivariate_run_id, {})
    service.complete("user-a", str(started["run_id"]))

    assert service.status("user-a", str(started["run_id"]))["status"] == "complete"
    artifacts = service.artifacts("user-a", str(started["run_id"]))
    snapshot = artifacts["input_snapshot"]
    assert snapshot["availability_reasons"] == []
    assert len(snapshot["listing_keys"]) == 5
    assert snapshot["policy"]["allowed_distribution_frequencies"] == [
        "monthly",
        "quarterly",
        "semiannual",
    ]
    candidates = service.candidates("user-a", str(started["run_id"]))["items"]
    assert all("input_snapshot_unavailable" not in candidate["reasons"] for candidate in candidates)
    baselines = [candidate for candidate in candidates if candidate["baseline"]]
    assert baselines
    assert all(candidate["status"] == "feasible" for candidate in baselines)
    assert all(len(candidate["weights"]) == 5 for candidate in baselines)


def test_multivariate_service_reserves_interactive_cpu_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import portfell.hosted_multivariate_service as service_module

    worker_counts: list[int] = []

    class InlineProcessPoolExecutor:
        def __init__(self, *, max_workers: int) -> None:
            worker_counts.append(max_workers)

        def __enter__(self) -> InlineProcessPoolExecutor:
            return self

        def __exit__(self, *args: object) -> None:
            del args

        def map(
            self, function: Callable[[object], object], values: Iterable[object]
        ) -> Iterator[object]:
            return map(function, values)

    monkeypatch.setattr(service_module, "ProcessPoolExecutor", InlineProcessPoolExecutor)
    state, data, project_id, bivariate_run_id = _fixtures()
    service = _service(state, data, _Persistence(), worker_count=lambda: 7)
    started = service.start("user-a", project_id, bivariate_run_id, {})

    service.complete("user-a", str(started["run_id"]))

    assert worker_counts == [4]
    assert service.status("user-a", str(started["run_id"]))["status"] == "complete"


def test_multivariate_service_rejects_bivariate_run_owned_by_another_user() -> None:
    state, data, project_id, bivariate_run_id = _fixtures()
    state.bivariate_runs_by_id[bivariate_run_id] = ResearchRun(
        bivariate_run_id, "user-b", "source", "complete", (), 1, 1
    )
    service = _service(state, data, _Persistence())

    try:
        service.start("user-a", project_id, bivariate_run_id, {})
    except Exception as error:
        assert "not_found" in str(error)
    else:
        raise AssertionError("cross-user bivariate runs must not be usable")


def test_multivariate_plan_authorizes_an_injected_project_repository() -> None:
    state, data, project_id, bivariate_run_id = _fixtures()
    state.projects_by_id = {}
    metadata_selection = state.selections_by_id.pop("metadata-selection-a")
    repository = InMemoryProjectRepository()
    repository.create_project(TenantProject(project_id, "user-a", "A"))
    selections = InMemorySelectionRepository()
    selections.create(
        TenantSelection(
            metadata_selection.selection_id,
            metadata_selection.project_id,
            metadata_selection.user_id,
            metadata_selection.name,
            metadata_selection.member_ids,
        )
    )
    service = MultivariateResearchService(
        data,
        _Persistence(),
        HostedResearchRepository(
            state, project_repository=repository, selection_repository=selections
        ),
        repository,
        selections,
        LocalMultivariateRunRepository(state),
        lambda: state.all_isins_rows,
        lambda: 1,
        None,
    )

    assert state.selections_by_id == {}
    assert service.plan("user-a", project_id, bivariate_run_id, {})["allowed"] is True


def test_multivariate_artifacts_survive_workspace_restart(
    tmp_path: Path,
) -> None:
    state, data, project_id, bivariate_run_id = _fixtures()
    store = LocalWorkspaceStore(tmp_path / "workspace.json")
    state.workspace_store = store
    service = _service(state, data, _Persistence())
    started = service.start("user-a", project_id, bivariate_run_id, {})
    service.complete("user-a", str(started["run_id"]))
    persist_local_workspace(state)

    restored = HostedApiState()
    restore_local_workspace(restored, store.load())
    run = restored.multivariate_runs_by_id[str(started["run_id"])]

    assert run.status == "complete"
    assert run.artifacts["input_snapshot"]["snapshot_id"] == run.input_snapshot_id
    assert restored.current_multivariate_run_by_project[project_id] == started["run_id"]


def test_multivariate_service_covers_idempotency_stale_and_error_boundaries() -> None:
    state, data, project_id, bivariate_run_id = _fixtures()
    persistence = _Persistence()
    service = _service(state, data, persistence)

    state.bivariate_runs_by_id[bivariate_run_id] = ResearchRun(
        bivariate_run_id,
        "user-a",
        bivariate_source_id(next(iter(state.univariate_selections_by_id.values()))),
        "running",
        (),
        0,
        10,
    )
    assert service.plan("user-a", project_id, bivariate_run_id, {})["allowed"] is False
    try:
        service.start("user-a", project_id, bivariate_run_id, {})
    except Exception as error:
        assert "bivariate_run_not_complete" in str(error)
    else:
        raise AssertionError("an incomplete bivariate run must be rejected")

    state.bivariate_runs_by_id[bivariate_run_id] = ResearchRun(
        bivariate_run_id,
        "user-a",
        bivariate_source_id(next(iter(state.univariate_selections_by_id.values()))),
        "complete",
        (),
        10,
        10,
    )
    first = service.start("user-a", project_id, bivariate_run_id, {})
    assert state.multivariate_runs_by_id[str(first["run_id"])].logical_hash == stable_hash(
        {
            "project_id": project_id,
            "bivariate_run_id": bivariate_run_id,
            "selection_id": "univariate-selection-a",
            "settings": {},
            "income_contract": INCOME_CONTRACT.qualified_name,
            "execution_contract": "multivariate_execution.v14",
        }
    )
    assert service.start("user-a", project_id, bivariate_run_id, {})["run_id"] == first["run_id"]
    second = service.start("user-a", project_id, bivariate_run_id, {"max_weight": 0.2})
    assert state.multivariate_runs_by_id[str(first["run_id"])].status == "stale"
    service.complete("user-a", str(second["run_id"]))
    assert service.structure("user-a", str(second["run_id"]))
    assert service.validation("user-a", str(second["run_id"]))["items"]
    assert service.components("user-a", str(second["run_id"]), 999, -1)["limit"] == 100
    assert service.risk_contributions("user-a", str(second["run_id"]), "missing")["items"] == []
    try:
        service.candidate_detail("user-a", str(second["run_id"]), "missing")
    except Exception as error:
        assert "not_found" in str(error)
    else:
        raise AssertionError("unknown candidate ids must be rejected")
    service.complete("user-a", str(second["run_id"]))


def test_multivariate_service_expires_abandoned_running_runs() -> None:
    state, data, project_id, bivariate_run_id = _fixtures()
    persistence = _Persistence()
    service = _service(state, data, persistence)
    started = service.start("user-a", project_id, bivariate_run_id, {})
    run_id = str(started["run_id"])
    state.multivariate_runs_by_id[run_id] = replace(
        state.multivariate_runs_by_id[run_id],
        started_at_epoch=0,
    )

    status = service.status("user-a", run_id)

    assert status["status"] == "failed"
    assert status["failure_reason"] == "compute_timeout"
    assert status["estimated_remaining_seconds"] == 0
    assert persistence.persisted >= 2


def test_multivariate_service_restarts_a_failed_logical_run() -> None:
    state, data, project_id, bivariate_run_id = _fixtures()
    service = _service(state, data, _Persistence())
    started = service.start("user-a", project_id, bivariate_run_id, {})
    run_id = str(started["run_id"])
    state.multivariate_runs_by_id[run_id] = replace(
        state.multivariate_runs_by_id[run_id],
        status="failed",
        phase="failed",
        failure_reason="temporary_failure",
    )

    restarted = service.start("user-a", project_id, bivariate_run_id, {})

    assert restarted["run_id"] == run_id
    assert restarted["status"] == "running"
    assert restarted["phase"] == "resolve_inputs"
    assert restarted["failure_reason"] is None


def test_multivariate_service_rejects_missing_dependency_closure_and_marks_failures() -> None:
    state, data, project_id, bivariate_run_id = _fixtures()
    service = _service(state, data, _Persistence())
    state.univariate_selections_by_id.clear()
    try:
        service.plan("user-a", project_id, bivariate_run_id, {})
    except Exception as error:
        assert "bivariate_dependency_mismatch" in str(error)
    else:
        raise AssertionError("a bivariate run needs exactly one matching selection")

    state, data, project_id, bivariate_run_id = _fixtures()
    service = _service(state, data, _Persistence())
    state.selections_by_id.clear()
    try:
        service.plan("user-a", project_id, bivariate_run_id, {})
    except Exception as error:
        assert "project_metadata_dependency_mismatch" in str(error)
    else:
        raise AssertionError("a project needs exactly one metadata selection")

    state, data, project_id, bivariate_run_id = _fixtures()
    service = _service(state, data, _Persistence())
    state.univariate_runs_by_id["univariate-a"] = ResearchRun(
        "univariate-a", "user-a", "wrong-source", "complete", (), 5, 5
    )
    started = service.start("user-a", project_id, bivariate_run_id, {"variant": "bad-source"})
    service.complete("user-a", str(started["run_id"]))
    assert service.status("user-a", str(started["run_id"]))["status"] == "failed"
    service._advance("user-a", "unknown-run", "build_risk_model", 1)  # pyright: ignore[reportPrivateUsage]


def test_multivariate_service_accepts_a_published_shared_market_univariate_run() -> None:
    state, data, project_id, bivariate_run_id = _fixtures()
    state.quote_run_by_univariate_run_id.clear()
    source = univariate_source_id("metadata-selection-a", "shared-market")
    existing = state.univariate_runs_by_id["univariate-a"]
    state.univariate_runs_by_id["univariate-a"] = ResearchRun(
        "univariate-a", "user-a", source, "complete", existing.rows, 5, 5
    )
    service = _service(state, data, _Persistence())

    started = service.start("user-a", project_id, bivariate_run_id, {})
    service.complete("user-a", str(started["run_id"]))

    completed = service.status("user-a", str(started["run_id"]))
    assert completed["status"] == "complete"
    artifacts = service.artifacts("user-a", str(started["run_id"]))
    quote_ids = artifacts["input_snapshot"]["quote_artifact_ids"]
    assert all(source in artifact_id for _, artifact_id in quote_ids)


def test_multivariate_service_refits_candidates_for_walk_forward_validation() -> None:
    state, data, project_id, bivariate_run_id = _fixtures()
    start = date(2023, 1, 1)
    extended_quotes = tuple(
        {
            "isin": f"IE{index}",
            "exchange": "X",
            "code": f"ETF{index}",
            "date": (start + timedelta(days=day)).isoformat(),
            "adjusted_close": 100 + index * 5 + day * (0.03 + index * 0.001),
        }
        for index in range(5)
        for day in range(505, 526)
    )
    service = _service(
        state, _Data((*data.quotes, *extended_quotes), data.dividends), _Persistence()
    )
    started = service.start("user-a", project_id, bivariate_run_id, {})
    service.complete("user-a", str(started["run_id"]))
    validation = service.validation("user-a", str(started["run_id"]))["items"]
    assert any(item["kind"] == "walk_forward" and item["risk_model_id"] for item in validation)
    json.dumps(validation)
