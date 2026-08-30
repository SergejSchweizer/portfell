from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

import portfell.hosted_api_local_runtime as local_runtime_module
import portfell.hosted_bivariate_service as bivariate_service_module
from portfell.bivariate_diagnostics import (
    bivariate_metric_summary,
    covariance_diagnostics,
    downside_diagnostics,
    pearson_diagnostics,
    spearman_diagnostics,
)
from portfell.bivariate_views import build_bivariate_summary, build_covariance_matrix
from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_local_runtime import LocalHostedRuntime
from portfell.hosted_api_service_support import stable_hash
from portfell.hosted_api_state import HostedApiState, SelectionRecord
from portfell.hosted_bivariate_service import BivariateResearchService
from portfell.hosted_research_ports import ResearchDataset, UnivariateProgress
from portfell.hosted_research_repository import HostedResearchRepository
from portfell.hosted_research_workflow import (
    HostedResearchError,
    ResearchRun,
    UnivariateSelection,
    bivariate_source_id,
)
from portfell.hosted_univariate_service import UnivariateResearchService
from portfell.paths import LakePaths
from portfell.table_io import JsonRow, read_rows, write_rows


@dataclass
class FakeResearchData:
    univariate_rows: tuple[JsonRow, ...]
    selected_calls: list[tuple[tuple[str, ...], ResearchDataset]]
    selected_result: tuple[JsonRow, ...] = ()

    def selected_rows(
        self, member_ids: tuple[str, ...], *, dataset: ResearchDataset
    ) -> tuple[JsonRow, ...]:
        self.selected_calls.append((member_ids, dataset))
        return self.selected_result

    def has_selected_rows(self, member_ids: tuple[str, ...], *, dataset: ResearchDataset) -> bool:
        self.selected_calls.append((member_ids, dataset))
        return bool(self.selected_result)

    def build_univariate_rows(
        self,
        member_ids: tuple[str, ...],
        *,
        on_progress: UnivariateProgress | None = None,
    ) -> tuple[JsonRow, ...]:
        if on_progress is not None:
            for completed, _member_id in enumerate(member_ids, start=1):
                on_progress(completed)
        return self.univariate_rows


@dataclass
class RecordingPersistence:
    calls: int = 0

    def persist(self) -> None:
        self.calls += 1


def test_univariate_service_uses_injected_data_and_persistence_ports() -> None:
    member_id = "IE1:XETRA:AAA"
    selection = SelectionRecord("selection-1", "user-a", "project-1", "UCITS", (member_id,))
    state = HostedApiState(selections_by_id={selection.selection_id: selection})
    data = FakeResearchData(
        univariate_rows=(
            {
                "isin": "IE1",
                "exchange": "XETRA",
                "code": "AAA",
                "observation_count": 100,
            },
        ),
        selected_calls=[],
        selected_result=({"isin": "IE1", "exchange": "XETRA", "code": "AAA"},),
    )
    persistence = RecordingPersistence()
    service = UnivariateResearchService(HostedResearchRepository(state), data, persistence)

    started = service.start("user-a", selection.selection_id)
    service.complete("user-a", selection.selection_id)

    completed = state.univariate_runs_by_id[str(started["run_id"])]
    assert completed.status == "complete"
    assert completed.rows == data.univariate_rows
    assert state.current_univariate_selection_by_user["user-a"] in state.univariate_selections_by_id
    assert data.selected_calls == [(selection.member_ids, "quotes")]
    assert persistence.calls == 1


def test_univariate_service_covers_reuse_failure_and_in_memory_paths() -> None:
    member_id = "IE1:XETRA:AAA"
    selection = SelectionRecord("selection-1", "user-a", "project-1", "UCITS", (member_id,))
    state = HostedApiState(selections_by_id={selection.selection_id: selection})
    data = FakeResearchData(
        (),
        [],
        selected_result=({"isin": "IE1", "exchange": "XETRA", "code": "AAA"},),
    )
    persistence = RecordingPersistence()
    repository = HostedResearchRepository(state)
    service = UnivariateResearchService(repository, data, persistence)

    started = service.start("user-a", selection.selection_id)
    run_id = str(started["run_id"])
    source_id = state.univariate_runs_by_id[run_id].source_id
    state.univariate_runs_by_id[run_id] = ResearchRun(
        run_id, "user-a", source_id, "failed", (), 1, 0, 1
    )
    restarted = service.start("user-a", selection.selection_id)
    assert restarted["status"] == "running"
    service.complete("user-a", selection.selection_id)
    assert state.univariate_runs_by_id[run_id].status == "failed"
    assert persistence.calls == 1

    state.univariate_runs_by_id[run_id] = ResearchRun(
        run_id, "user-a", source_id, "running", (), 1, 0
    )
    data.univariate_rows = (
        {"isin": "IE1", "exchange": "XETRA", "code": "AAA", "observation_count": 4},
    )
    service.complete("user-a", selection.selection_id)
    service.complete("user-a", selection.selection_id)
    assert state.univariate_runs_by_id[run_id].status == "complete"
    assert data.selected_calls[-1] == (selection.member_ids, "quotes")
    assert service.results("user-a", run_id, 10, 0)["total"] == 1
    with pytest.raises(HostedApplicationError, match="predicates_required"):
        service.apply_selection("user-a", run_id, [])
    current_id = state.current_univariate_selection_by_user["user-a"]
    assert service.selection_results("user-a", current_id, 10, 0)["total"] == 1


def test_univariate_service_marks_the_run_failed_when_computation_raises() -> None:
    class FailingResearchData(FakeResearchData):
        def build_univariate_rows(
            self,
            member_ids: tuple[str, ...],
            *,
            on_progress: UnivariateProgress | None = None,
        ) -> tuple[JsonRow, ...]:
            _ = member_ids, on_progress
            raise RuntimeError("lake unavailable")

    selection = SelectionRecord("selection-1", "user-a", "project-1", "UCITS", ("IE1:XETRA:AAA",))
    state = HostedApiState(selections_by_id={selection.selection_id: selection})
    data = FailingResearchData((), [], selected_result=({"isin": "IE1"},))
    persistence = RecordingPersistence()
    service = UnivariateResearchService(HostedResearchRepository(state), data, persistence)

    started = service.start("user-a", selection.selection_id)
    with pytest.raises(RuntimeError, match="lake unavailable"):
        service.complete("user-a", selection.selection_id)

    assert state.univariate_runs_by_id[str(started["run_id"])].status == "failed"
    assert persistence.calls == 1


def test_univariate_service_uses_published_shared_rows_without_a_quote_run() -> None:
    selection = SelectionRecord("selection-1", "user-a", "project-1", "UCITS", ("IE1:XETRA:AAA",))
    state = HostedApiState(selections_by_id={selection.selection_id: selection})
    data = FakeResearchData(
        ({"isin": "IE1", "exchange": "XETRA", "code": "AAA", "observation_count": 4},),
        [],
        selected_result=({"isin": "IE1", "exchange": "XETRA", "code": "AAA"},),
    )
    service = UnivariateResearchService(
        HostedResearchRepository(state), data, RecordingPersistence()
    )

    started = service.start("user-a", selection.selection_id)
    service.complete("user-a", selection.selection_id)

    assert started["status"] == "running"
    assert state.univariate_runs_by_id[str(started["run_id"])].status == "complete"
    assert data.selected_calls[0] == (selection.member_ids, "quotes")


def test_univariate_service_versions_the_calculation_run_identity() -> None:
    selection = SelectionRecord("selection-1", "user-a", "project-1", "UCITS", ("IE1:XETRA:AAA",))
    state = HostedApiState(selections_by_id={selection.selection_id: selection})
    data = FakeResearchData((), [], selected_result=({"isin": "IE1"},))
    service = UnivariateResearchService(
        HostedResearchRepository(state), data, RecordingPersistence()
    )

    started = service.start("user-a", selection.selection_id)
    run = state.univariate_runs_by_id[str(started["run_id"])]

    assert run.source_id == stable_hash(
        {
            "selection_id": selection.selection_id,
            "quote_run_id": "market-source",
            "calculation_contract": "univariate.statistics.v2",
        }
    )


def test_bivariate_source_identity_versions_the_algorithm() -> None:
    selection = UnivariateSelection(
        "selection-a",
        "user-a",
        "univariate-a",
        ("IE1:XETRA:AAA", "IE2:XETRA:BBB"),
        (),
        (),
        2,
    )

    assert bivariate_source_id(selection) == stable_hash(
        {
            "selection_id": selection.selection_id,
            "members": list(selection.member_ids),
            "algorithm_version": "v10",
        }
    )


def test_bivariate_service_covers_plan_reuse_and_failure_transitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    one = UnivariateSelection("one", "user-a", "uni", ("IE1:XETRA:AAA",), (), (), 1)
    two = UnivariateSelection(
        "two",
        "user-a",
        "uni",
        ("IE1:XETRA:AAA", "IE2:XETRA:BBB"),
        (),
        (),
        2,
    )
    univariate = ResearchRun("uni", "user-a", "source", "complete", (), 2, 2)
    state = HostedApiState(
        univariate_runs_by_id={univariate.run_id: univariate},
        univariate_selections_by_id={one.selection_id: one, two.selection_id: two},
    )
    data = FakeResearchData((), [])
    persistence = RecordingPersistence()
    service = BivariateResearchService(HostedResearchRepository(state), data, persistence)

    with pytest.raises(HostedApplicationError, match="pair_plan_not_runnable"):
        service.start("user-a", one.selection_id)
    started = service.start("user-a", two.selection_id)
    assert service.start("user-a", two.selection_id)["run_id"] == started["run_id"]
    service.complete("user-a", two.selection_id)
    assert state.bivariate_runs_by_id[str(started["run_id"])].status == "failed"
    assert persistence.calls == 1

    source_id = state.bivariate_runs_by_id[str(started["run_id"])].source_id
    state.bivariate_runs_by_id[str(started["run_id"])] = ResearchRun(
        str(started["run_id"]), "user-a", source_id, "running", (), 1, 0
    )
    data.selected_result = ({"isin": "IE1"},)

    def fail_run(**_kwargs: object) -> ResearchRun:
        raise HostedResearchError("failed")

    monkeypatch.setattr(bivariate_service_module, "create_bivariate_run", fail_run)
    service.complete("user-a", two.selection_id)
    assert state.bivariate_runs_by_id[str(started["run_id"])].status == "failed"

    orphan = ResearchRun("orphan", "user-a", "unmatched", "complete", (), 0, 0)
    state.bivariate_runs_by_id[orphan.run_id] = orphan
    with pytest.raises(HostedApplicationError, match="not_found"):
        service.covariance_matrix("user-a", orphan.run_id)


def test_bivariate_service_uses_shared_market_quotes_without_a_quote_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection = UnivariateSelection(
        "two",
        "user-a",
        "uni",
        ("IE1:XETRA:AAA", "IE2:XETRA:BBB"),
        (),
        (),
        2,
    )
    univariate = ResearchRun("uni", "user-a", "source", "complete", (), 2, 2)
    state = HostedApiState(
        univariate_runs_by_id={univariate.run_id: univariate},
        univariate_selections_by_id={selection.selection_id: selection},
    )
    shared_quotes = ({"isin": "IE1"}, {"isin": "IE2"})
    data = FakeResearchData((), [], selected_result=shared_quotes)
    service = BivariateResearchService(
        HostedResearchRepository(state), data, RecordingPersistence()
    )
    captured: dict[str, object] = {}

    def compute_from_shared_quotes(**kwargs: object) -> ResearchRun:
        captured.update(kwargs)
        return ResearchRun("computed", "user-a", "source", "complete", (), 1, 1)

    monkeypatch.setattr(
        bivariate_service_module, "create_bivariate_run", compute_from_shared_quotes
    )

    started = service.start("user-a", selection.selection_id)
    service.complete("user-a", selection.selection_id)

    assert state.bivariate_runs_by_id[str(started["run_id"])].status == "complete"
    assert captured["quote_rows"] == shared_quotes
    assert data.selected_calls == [(selection.member_ids, "quotes")]


def test_local_research_adapter_builds_rows_and_reports_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFELL_LAKE_ROOT", str(tmp_path))
    runtime = LocalHostedRuntime(
        quote_workflow=lambda **_kwargs: {},
        metadata_workflow=lambda **_kwargs: {},
        cpu_count=lambda: 2,
    )

    class InlineExecutor:
        def __init__(self, *, max_workers: int) -> None:
            assert max_workers == 2

        def __enter__(self) -> InlineExecutor:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def map(self, *_args: object) -> tuple[JsonRow | None, ...]:
            return (None, {"isin": "IE2"})

    monkeypatch.setattr(local_runtime_module, "ProcessPoolExecutor", InlineExecutor)
    progress: list[int] = []

    rows = runtime.build_univariate_rows(
        ("IE1:XETRA:AAA", "IE2:XETRA:BBB"), on_progress=progress.append
    )

    assert rows == ({"isin": "IE2"},)
    assert progress == [1, 2]


def test_local_univariate_worker_handles_missing_computed_and_cached_rows(tmp_path: Path) -> None:
    paths = LakePaths(root=tmp_path)
    member_id = "IE1:XETRA:AAA"
    assert local_runtime_module._build_scoped_univariate_listing(tmp_path, member_id) is None

    quote_rows = [
        {
            "isin": "IE1",
            "exchange": "XETRA",
            "code": "AAA",
            "date": f"2026-01-0{day}",
            "adjusted_close": 100.0 + day,
        }
        for day in range(1, 5)
    ]
    write_rows(paths.silver_quote_file("XETRA", "IE1"), quote_rows)
    computed = local_runtime_module._build_scoped_univariate_listing(tmp_path, member_id)
    assert computed is not None
    write_rows(
        paths.gold_univariate_statistics("XETRA", "IE1"),
        [
            {
                **computed,
                "distribution_frequency": "stale",
                "annual_dividend_yield": -1.0,
            }
        ],
    )

    cached = local_runtime_module._build_scoped_univariate_listing(tmp_path, member_id)

    assert cached is not None
    assert cached["distribution_frequency"] == "accumulating"
    assert read_rows(paths.gold_univariate_statistics("XETRA", "IE1")) == [cached]

    legacy = {key: value for key, value in cached.items() if key != "calculation_contract"}
    legacy["total_return"] = -1.0
    write_rows(paths.gold_univariate_statistics("XETRA", "IE1"), [legacy])

    recomputed = local_runtime_module._build_scoped_univariate_listing(tmp_path, member_id)

    assert recomputed is not None
    assert recomputed["calculation_contract"] == "univariate.statistics.v2"
    assert recomputed["total_return"] != -1.0

    revised_quotes = [
        {**row, "adjusted_close": float(row["adjusted_close"]) + 10.0} for row in quote_rows
    ]
    write_rows(paths.silver_quote_file("XETRA", "IE1"), revised_quotes)

    revised = local_runtime_module._build_scoped_univariate_listing(tmp_path, member_id)

    assert revised is not None
    assert revised["quote_input_id"] != recomputed["quote_input_id"]


def test_bivariate_read_models_cover_empty_and_constant_inputs() -> None:
    assert bivariate_metric_summary([])["histogram"] == []
    assert bivariate_metric_summary([0.5, 0.5])["histogram"][0]["count"] == 2
    assert pearson_diagnostics(())["high_70_pairs"] == 0
    assert spearman_diagnostics(())["high_70_pairs"] == 0
    assert downside_diagnostics(())["high_70_pairs"] == 0
    assert covariance_diagnostics((), [], 0)["listing_count"] == 0
    assert build_bivariate_summary(())["observation_count"] == 0
    assert build_bivariate_summary(())["date_start"] == ""
    assert build_bivariate_summary(())["date_end"] == ""
    assert build_covariance_matrix((), ())["observation_count"] == 0
    assert build_covariance_matrix((), ())["date_start"] == ""
    assert build_covariance_matrix((), ())["date_end"] == ""


def test_diagnostics_ignore_missing_pair_metrics() -> None:
    rows: tuple[JsonRow, ...] = (
        {
            "left_isin": "IE1",
            "left_exchange": "XETRA",
            "left_code": "AAA",
            "right_isin": "IE2",
            "right_exchange": "XETRA",
            "right_code": "BBB",
            "pearson_correlation": None,
            "spearman_correlation": None,
            "downside_correlation": None,
        },
    )
    assert pearson_diagnostics(rows)["negative_pairs"] == 0
    assert spearman_diagnostics(rows)["negative_pairs"] == 0
    assert downside_diagnostics(rows)["negative_pairs"] == 0
