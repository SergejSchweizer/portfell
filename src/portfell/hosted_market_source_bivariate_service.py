"""Bivariate research service backed exclusively by one external market snapshot."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Protocol, cast

from portfell.bivariate_views import build_covariance_matrix_from_rows
from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_serializers import research_run_row
from portfell.hosted_api_service_support import opaque_id
from portfell.hosted_bivariate_service import BivariateResearchService
from portfell.hosted_research_ports import (
    ResearchDataPort,
    ResearchPersistencePort,
    ResearchRunRepository,
)
from portfell.hosted_research_workflow import (
    HostedResearchError,
    ResearchRun,
    UnivariateSelection,
    bivariate_source_id,
    create_bivariate_run,
    pair_plan,
)
from portfell.market_source.contracts import ListingKey
from portfell.market_source.errors import (
    MARKET_SOURCE_CONTRACT_MISMATCH,
    MARKET_SOURCE_INVALID_VALUE,
    MARKET_SOURCE_UNAVAILABLE,
    MarketSourceError,
)
from portfell.market_source.gateway import MarketDataSnapshot
from portfell.market_source.projection import MarketProjectionError, project_market_inputs
from portfell.market_source.snapshot import build_market_source_snapshot
from portfell.table_io import JsonRow


class BivariateSnapshotGateway(Protocol):
    def read_snapshot(
        self,
        keys: Sequence[ListingKey],
        *,
        start: date,
        end: date,
    ) -> MarketDataSnapshot: ...


@dataclass(frozen=True)
class BivariateMarketSnapshot:
    snapshot_id: str
    quotes: tuple[JsonRow, ...]


class BivariateMarketSourceData:
    """Project selected quote rows from one coherent gateway snapshot."""

    def __init__(self, gateway: BivariateSnapshotGateway) -> None:
        self._gateway = gateway

    def read(self, member_ids: tuple[str, ...]) -> BivariateMarketSnapshot:
        keys = _listing_keys(member_ids)
        source = self._gateway.read_snapshot(keys, start=date.min, end=date.max)
        expected = set(keys)
        if {listing.key for listing in source.listings} != expected:
            raise MarketSourceError(MARKET_SOURCE_CONTRACT_MISMATCH)
        if not expected.issubset({quote.key for quote in source.quotes}):
            raise MarketSourceError(MARKET_SOURCE_UNAVAILABLE)
        lineage = build_market_source_snapshot(
            listings=source.listings,
            quotes=source.quotes,
            dividends=source.dividends,
            splits=source.splits,
        )
        projected = project_market_inputs(
            quotes=source.quotes,
            dividends=source.dividends,
            splits=source.splits,
        )
        return BivariateMarketSnapshot(lineage.snapshot_id, projected.quotes)


class MarketSourceBivariateResearchService(BivariateResearchService):
    """Run Bivariate without quote-run or shared-market lookups."""

    def __init__(
        self,
        repository: ResearchRunRepository,
        data: BivariateMarketSourceData,
        persistence: ResearchPersistencePort,
        workflow_projector: Callable[[str, str], object] | None = None,
    ) -> None:
        super().__init__(repository, cast(ResearchDataPort, data), persistence, workflow_projector)
        self._market_data = data

    def start(self, user_id: str, selection_id: str) -> JsonRow:
        selection = self._repository.univariate_selection(selection_id, user_id)
        plan = pair_plan(selection)
        if not plan["allowed"]:
            raise HostedApplicationError(422, "pair_plan_not_runnable")
        market = self._read_market(selection.member_ids)
        source = _market_source_id(selection, market.snapshot_id)
        run_id = opaque_id("bivariate-run", f"{user_id}:{source}")
        existing = self._repository.find_bivariate_run(run_id, user_id)
        if existing is not None and existing.status == "running":
            return research_run_row(existing)
        run = ResearchRun(
            run_id=run_id,
            user_id=user_id,
            source_id=source,
            status="running",
            rows=(),
            total=int(plan["theoretical_pair_count"]),
            completed=0,
        )
        self._repository.save_bivariate_run(run)
        project_id = self._repository.project_id_for_run(
            user_id=user_id, run_id=selection.source_run_id
        )
        if project_id is not None:
            self._repository.bind_project_run(
                user_id=user_id, project_id=project_id, run_id=run.run_id
            )
            self._project(user_id, project_id)
        self._repository.audit(user_id, "bivariate_statistics.start")
        return research_run_row(run)

    def complete(self, user_id: str, selection_id: str) -> None:
        run: ResearchRun | None = None
        try:
            selection = self._repository.univariate_selection(selection_id, user_id)
            market = self._read_market(selection.member_ids)
            source = _market_source_id(selection, market.snapshot_id)
            run_id = opaque_id("bivariate-run", f"{user_id}:{source}")
            run = self._repository.bivariate_run(run_id, user_id)
            if run.status != "running":
                return

            def update_progress(completed: int, total: int) -> None:
                active = self._repository.find_bivariate_run(run_id, user_id)
                if active is not None and active.status == "running":
                    self._repository.save_bivariate_run(
                        replace(active, completed=min(completed, total), total=total)
                    )
                    project_id = self._repository.project_id_for_run(user_id=user_id, run_id=run_id)
                    if project_id is not None:
                        self._project(user_id, project_id)

            computed = create_bivariate_run(
                user_id=user_id,
                selection=selection,
                quote_rows=market.quotes,
                on_progress=update_progress,
            )
            self._repository.save_bivariate_run(
                replace(
                    computed,
                    run_id=run_id,
                    source_id=source,
                    total=computed.total,
                    completed=computed.total,
                )
            )
            project_id = self._repository.project_id_for_run(user_id=user_id, run_id=run_id)
            if project_id is not None:
                self._project(user_id, project_id)
            self._repository.audit(user_id, "bivariate_statistics.complete")
            self._persistence.persist()
        except HostedResearchError:
            if run is not None:
                self._fail(run, user_id)
        except Exception:
            if run is not None:
                self._fail(run, user_id)
            raise

    def covariance_matrix(self, user_id: str, run_id: str) -> JsonRow:
        """Read the scoped run directly; its source identity already includes snapshot lineage."""
        run = self._repository.bivariate_run(run_id, user_id)
        return build_covariance_matrix_from_rows(run.rows)

    def _read_market(self, member_ids: tuple[str, ...]) -> BivariateMarketSnapshot:
        try:
            return self._market_data.read(member_ids)
        except (MarketSourceError, MarketProjectionError) as error:
            raise HostedApplicationError(409, error.code) from error


def _market_source_id(selection: UnivariateSelection, snapshot_id: str) -> str:
    """Keep both upstream-selection and source-snapshot lineage inspectable."""
    return f"{bivariate_source_id(selection)}::{snapshot_id}"


def _listing_keys(member_ids: tuple[str, ...]) -> tuple[ListingKey, ...]:
    keys: list[ListingKey] = []
    for member_id in member_ids:
        parts = member_id.split(":")
        if len(parts) != 3 or not all(parts):
            raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
        keys.append(ListingKey(parts[0], parts[1], parts[2]))
    if len(set(keys)) != len(keys):
        raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
    return tuple(sorted(keys))


__all__ = ["BivariateMarketSourceData", "MarketSourceBivariateResearchService"]
