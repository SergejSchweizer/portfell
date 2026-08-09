from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from portfell.hosted_api_state import HostedApiState, ProjectRecord
from portfell.hosted_multivariate_service import MultivariateResearchService
from portfell.hosted_research_workflow import (
    ResearchRun,
    UnivariateSelection,
    bivariate_source_id,
)
from portfell.table_io import JsonRow


@dataclass
class _Data:
    quotes: tuple[JsonRow, ...]
    dividends: tuple[JsonRow, ...]

    def selected_rows(self, member_ids: tuple[str, ...], *, dataset: str) -> tuple[JsonRow, ...]:
        del member_ids
        return self.quotes if dataset == "quotes" else self.dividends

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
        all_isins_rows=tuple(
            {"isin": isin, "exchange": exchange, "code": code, "instrument_type": "ETF"}
            for isin, exchange, code in keys
        ),
        univariate_runs_by_id={
            univariate_run_id: ResearchRun(
                univariate_run_id, user_id, "source", "complete", rows, 5, 5
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
    service = MultivariateResearchService(state, data, persistence)

    started = service.start("user-a", project_id, bivariate_run_id, {})
    service.complete("user-a", str(started["run_id"]))
    status = service.status("user-a", str(started["run_id"]))

    assert status["status"] == "complete"
    assert status["input_snapshot_id"]
    assert service.summary("user-a", str(started["run_id"]))["candidate_etf_count"] == 5
    candidates = service.candidates("user-a", str(started["run_id"]))["items"]
    assert len(candidates) == 6
    candidate_id = str(candidates[0]["candidate_id"])
    detail = service.candidate_detail("user-a", str(started["run_id"]), candidate_id)
    assert detail["candidate_id"] == candidate_id
    assert "total_return" in detail
    assert "max_drawdown" in detail
    assert service.risk_contributions("user-a", str(started["run_id"]), candidate_id)["items"]
    assert service.income_evidence("user-a", str(started["run_id"]))["items"]
    components = service.components("user-a", str(started["run_id"]), limit=3, offset=0)
    assert components["total"] == 25
    assert len(components["items"]) == 3
    assert state.current_multivariate_run_by_project[project_id] == started["run_id"]
    assert persistence.persisted >= 2


def test_multivariate_service_rejects_bivariate_run_owned_by_another_user() -> None:
    state, data, project_id, bivariate_run_id = _fixtures()
    state.bivariate_runs_by_id[bivariate_run_id] = ResearchRun(
        bivariate_run_id, "user-b", "source", "complete", (), 1, 1
    )
    service = MultivariateResearchService(state, data, _Persistence())

    try:
        service.start("user-a", project_id, bivariate_run_id, {})
    except Exception as error:
        assert "not_found" in str(error)
    else:
        raise AssertionError("cross-user bivariate runs must not be usable")
