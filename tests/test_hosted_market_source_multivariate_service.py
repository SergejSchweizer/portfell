from __future__ import annotations

import inspect
import json
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import pytest

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_state import HostedApiState, ProjectRecord, SelectionRecord
from portfell.hosted_local_project_repository import LocalProjectRepository
from portfell.hosted_local_selection_repository import LocalSelectionRepository
from portfell.hosted_market_source_multivariate_service import (
    MarketSourceMultivariateResearchService,
)
from portfell.hosted_market_source_research_data import MarketSourceResearchData
from portfell.hosted_multivariate_run_repository import LocalMultivariateRunRepository
from portfell.hosted_multivariate_service import MultivariateResearchService
from portfell.hosted_research_repository import HostedResearchRepository
from portfell.hosted_research_workflow import (
    ResearchRun,
    UnivariateSelection,
    bivariate_source_id,
    univariate_source_id,
)
from portfell.market_source.contracts import Dividend, EodQuote, Listing, ListingKey
from portfell.market_source.gateway import MarketDataSnapshot
from portfell.table_io import JsonRow


@dataclass
class _Persistence:
    persisted: int = 0

    def persist(self) -> None:
        self.persisted += 1


@dataclass
class _LegacyData:
    quotes: tuple[JsonRow, ...]
    dividends: tuple[JsonRow, ...]

    def selected_rows(self, member_ids: tuple[str, ...], *, dataset: str) -> tuple[JsonRow, ...]:
        del member_ids
        return self.quotes if dataset == "quotes" else self.dividends

    def has_selected_rows(self, member_ids: tuple[str, ...], *, dataset: str) -> bool:
        return bool(self.selected_rows(member_ids, dataset=dataset))

    def build_univariate_rows(
        self, member_ids: tuple[str, ...], **kwargs: object
    ) -> tuple[JsonRow, ...]:
        del member_ids, kwargs
        return ()


@dataclass
class _Gateway:
    snapshot: MarketDataSnapshot
    reads: int = 0

    def read_snapshot(
        self,
        keys: Sequence[ListingKey],
        *,
        start: date,
        end: date,
    ) -> MarketDataSnapshot:
        assert tuple(keys) == tuple(sorted(listing.key for listing in self.snapshot.listings))
        assert start == date.min
        assert end == date.max
        self.reads += 1
        return self.snapshot


def _source_snapshot(*, quote_bump: Decimal = Decimal("0")) -> MarketDataSnapshot:
    keys = tuple(ListingKey(f"IE{index}", "X", f"ETF{index}") for index in range(5))
    listings = tuple(
        Listing(
            key=key,
            name=key.code,
            instrument_type="ETF",
            country="IE",
            currency="EUR",
            is_active=True,
        )
        for key in keys
    )
    start = date(2023, 1, 1)
    quotes = tuple(
        EodQuote(
            key=key,
            trade_date=start + timedelta(days=day),
            adjusted_close=(
                Decimal("100")
                + Decimal(index * 5)
                + Decimal(day) * (Decimal("0.03") + Decimal(index) * Decimal("0.001"))
                + quote_bump
            ),
            close=(
                Decimal("100")
                + Decimal(index * 5)
                + Decimal(day) * (Decimal("0.03") + Decimal(index) * Decimal("0.001"))
                + quote_bump
            ),
            volume=Decimal("100"),
        )
        for index, key in enumerate(keys)
        for day in range(505)
    )
    dividends = tuple(
        Dividend(
            key=key,
            event_date=date(2024, month, 1),
            event_key=f"{key.code}-{month}",
            amount=Decimal("0.2") + Decimal(index) * Decimal("0.01"),
            currency="EUR",
        )
        for index, key in enumerate(keys)
        for month in range(1, 13)
    )
    return MarketDataSnapshot(listings=listings, quotes=quotes, dividends=dividends, splits=())


def _state(snapshot_id: str, *, market_bivariate: bool) -> tuple[HostedApiState, str, str]:
    user_id, project_id, univariate_run_id = "user-a", "project-a", "univariate-a"
    keys = tuple((f"IE{index}", "X", f"ETF{index}") for index in range(5))
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
                univariate_source_id("metadata-selection-a", snapshot_id),
                "complete",
                rows,
                5,
                5,
            )
        },
        univariate_selections_by_id={selection.selection_id: selection},
        quote_run_by_univariate_run_id={univariate_run_id: snapshot_id},
    )
    bivariate_run_id = "bivariate-a"
    base_source = bivariate_source_id(selection)
    source_id = f"{base_source}::{snapshot_id}" if market_bivariate else base_source
    state.bivariate_runs_by_id[bivariate_run_id] = ResearchRun(
        bivariate_run_id, user_id, source_id, "complete", (), 10, 10
    )
    return state, project_id, bivariate_run_id


def _legacy_service(state: HostedApiState, data: _LegacyData) -> MultivariateResearchService:
    return MultivariateResearchService(
        data,
        _Persistence(),
        HostedResearchRepository(state),
        LocalProjectRepository(state),
        LocalSelectionRepository(state),
        LocalMultivariateRunRepository(state),
        lambda: state.all_isins_rows,
        lambda: 1,
        None,
    )


def _market_service(
    state: HostedApiState, market_data: MarketSourceResearchData
) -> MarketSourceMultivariateResearchService:
    return MarketSourceMultivariateResearchService(
        market_data,
        _Persistence(),
        HostedResearchRepository(state),
        LocalProjectRepository(state),
        LocalSelectionRepository(state),
        LocalMultivariateRunRepository(state),
        lambda: state.all_isins_rows,
        lambda: 1,
        None,
    )


def _strip_lineage_ids(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_lineage_ids(item)
            for key, item in value.items()
            if not str(key).endswith("_id") and str(key) not in {"source_event_ids"}
        }
    if isinstance(value, (list, tuple)):
        return [_strip_lineage_ids(item) for item in value]
    return value


def _canonical_rows(rows: object) -> list[object]:
    """Compare unordered concurrent analytical rows by semantic content."""
    normalized = _strip_lineage_ids(rows)
    assert isinstance(normalized, list)
    return sorted(normalized, key=lambda row: json.dumps(row, sort_keys=True, default=str))


def test_market_source_multivariate_matches_legacy_calculation_on_exact_fixture() -> None:
    gateway = _Gateway(_source_snapshot())
    market_data = MarketSourceResearchData(gateway)
    member_ids = tuple(f"IE{index}:X:ETF{index}" for index in range(5))
    projected = market_data.read(member_ids)
    gateway.reads = 0

    legacy_state, project_id, bivariate_run_id = _state(
        projected.snapshot_id, market_bivariate=False
    )
    market_state, _, _ = _state(projected.snapshot_id, market_bivariate=True)
    legacy = _legacy_service(legacy_state, _LegacyData(projected.quotes, projected.dividends))
    market = _market_service(market_state, market_data)

    legacy_started = legacy.start("user-a", project_id, bivariate_run_id, {})
    market_started = market.start("user-a", project_id, bivariate_run_id, {})
    legacy_run = legacy_state.multivariate_runs_by_id[str(legacy_started["run_id"])]
    market_run = market_state.multivariate_runs_by_id[str(market_started["run_id"])]

    with ThreadPoolExecutor(max_workers=1) as executor:
        legacy_result = legacy._compute(  # pyright: ignore[reportPrivateUsage]
            legacy_run, executor=executor, on_phase=lambda *_args: None
        )
    with ThreadPoolExecutor(max_workers=1) as executor:
        market_result = market._compute(  # pyright: ignore[reportPrivateUsage]
            market_run, executor=executor, on_phase=lambda *_args: None
        )

    assert gateway.reads == 1
    legacy_risk = legacy_result.artifacts["risk_model"]
    market_risk = market_result.artifacts["risk_model"]
    assert market_risk["return_type"] == legacy_risk["return_type"] == "log"
    assert market_risk["covariance"] == legacy_risk["covariance"]
    assert _strip_lineage_ids(market_risk) == _strip_lineage_ids(legacy_risk)
    assert _canonical_rows(market_result.candidates) == _canonical_rows(legacy_result.candidates)
    assert _canonical_rows(market_result.validation) == _canonical_rows(legacy_result.validation)
    market_scorecards = tuple(
        row for row in market_result.validation if row.get("kind") == "scorecard"
    )
    legacy_scorecards = tuple(
        row for row in legacy_result.validation if row.get("kind") == "scorecard"
    )
    assert _canonical_rows(market_scorecards) == _canonical_rows(legacy_scorecards)
    assert market_result.summary["market_source_snapshot_id"] == projected.snapshot_id
    assert market_result.artifacts["market_source"] == {
        "snapshot_id": projected.snapshot_id,
        "split_event_count": 0,
        "split_policy": "lineage_only_no_return_adjustment",
    }
    assert all(
        projected.snapshot_id in artifact_id
        for _listing, artifact_id in market_result.artifacts["input_snapshot"]["quote_artifact_ids"]
    )
    assert all(
        projected.snapshot_id in artifact_id
        for _listing, artifact_id in market_result.artifacts["input_snapshot"][
            "dividend_artifact_ids"
        ]
    )


def test_market_source_multivariate_fails_closed_when_snapshot_changes() -> None:
    first_gateway = _Gateway(_source_snapshot())
    first_data = MarketSourceResearchData(first_gateway)
    member_ids = tuple(f"IE{index}:X:ETF{index}" for index in range(5))
    pinned = first_data.read(member_ids)

    state, project_id, bivariate_run_id = _state(pinned.snapshot_id, market_bivariate=True)
    changed_gateway = _Gateway(_source_snapshot(quote_bump=Decimal("1")))
    service = _market_service(state, MarketSourceResearchData(changed_gateway))
    started = service.start("user-a", project_id, bivariate_run_id, {})
    run = state.multivariate_runs_by_id[str(started["run_id"])]

    with (
        ThreadPoolExecutor(max_workers=1) as executor,
        pytest.raises(HostedApplicationError, match="market_source_snapshot_changed"),
    ):
        service._compute(  # pyright: ignore[reportPrivateUsage]
            run, executor=executor, on_phase=lambda *_args: None
        )


def test_market_source_multivariate_has_no_legacy_source_fallbacks() -> None:
    source = inspect.getsource(MarketSourceMultivariateResearchService._compute)

    assert "quote_run_id" not in source
    assert "quote_rows" not in source
    assert "selected_rows" not in source
    assert "shared-market" not in source
