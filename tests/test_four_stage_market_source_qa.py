"""Semantic cutover QA for the four market-backed research stages.

This is deliberately an application-level fixture rather than a repository SQL
test.  It proves that Metadata, Univariate, Bivariate and Multivariate consume
the same immutable external-market contract without reviving a local market
plane or reducing a listing identity to an ISIN.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import pytest

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_local_runtime import LocalHostedRuntime
from portfell.hosted_api_state import HostedApiState
from portfell.hosted_local_audit_event_repository import LocalAuditEventRepository
from portfell.hosted_local_metadata_repository import LocalMetadataLifecycleRepository
from portfell.hosted_local_project_repository import LocalProjectRepository
from portfell.hosted_local_selection_repository import LocalSelectionRepository
from portfell.hosted_market_source_bivariate_service import (
    BivariateMarketSourceData,
    MarketSourceBivariateResearchService,
)
from portfell.hosted_market_source_multivariate_service import (
    MarketSourceMultivariateResearchService,
)
from portfell.hosted_market_source_research_data import MarketSourceResearchData
from portfell.hosted_market_source_univariate_service import MarketSourceUnivariateResearchService
from portfell.hosted_metadata_project_service import MetadataProjectService, metadata_source_catalog
from portfell.hosted_multivariate_run_repository import LocalMultivariateRunRepository
from portfell.hosted_research_persistence import LocalResearchPersistence
from portfell.hosted_research_repository import HostedResearchRepository
from portfell.market_source.contracts import Dividend, EodQuote, Listing, ListingKey, Split
from portfell.market_source.gateway import MarketDataSnapshot
from portfell.market_source.projection import MISSING_ADJUSTED_CLOSE


def _empty_workflow(**_kwargs: object) -> dict[str, object]:
    return {}


@dataclass
class ImmutableGateway:
    """A source fixture that records coherent reads and never mutates its tables."""

    active: tuple[Listing, ...]
    snapshot: MarketDataSnapshot
    active_reads: int = 0
    snapshot_reads: int = 0

    def read_active_listings(self) -> tuple[Listing, ...]:
        self.active_reads += 1
        return self.active

    def read_snapshot(
        self, keys: Sequence[ListingKey], *, start: date, end: date
    ) -> MarketDataSnapshot:
        assert start == date.min
        assert end == date.max
        assert tuple(keys) == tuple(sorted(keys))
        assert set(keys) == {listing.key for listing in self.active}
        self.snapshot_reads += 1
        # ``by_keys`` is the production listing query: inactive/non-selected identities
        # cannot leak into an analytical snapshot even if they remain in source tables.
        return MarketDataSnapshot(
            self.active,
            self.snapshot.quotes,
            self.snapshot.dividends,
            self.snapshot.splits,
        )


def _fixture(*, missing_adjusted: bool = False) -> ImmutableGateway:
    active_keys = (
        # The first two are intentionally the same ISIN: full listing identity matters.
        ListingKey("IE00QA000001", "XETRA", "QA-A"),
        ListingKey("IE00QA000001", "XETRA", "QA-B"),
        ListingKey("IE00QA000003", "XETRA", "QA-C"),
        ListingKey("IE00QA000004", "XETRA", "QA-D"),
        ListingKey("IE00QA000005", "XETRA", "QA-E"),
    )
    active = tuple(
        Listing(key, f"Monthly {key.code}", "ETF", "IE", "EUR", True) for key in active_keys
    )
    inactive = Listing(
        ListingKey("IE00INACTIVE", "XETRA", "OLD"),
        "Inactive ETF",
        "ETF",
        "IE",
        "EUR",
        False,
    )
    first_day = date(2023, 1, 3)
    quotes = tuple(
        EodQuote(
            key,
            first_day + timedelta(days=offset),
            (
                None
                if missing_adjusted and key == active_keys[0] and offset == 0
                else Decimal("100")
                + Decimal(index * 7)
                + Decimal(offset) * (Decimal("0.031") + Decimal(index) / Decimal("1000"))
            ),
            Decimal("100")
            + Decimal(index * 7)
            + Decimal(offset) * (Decimal("0.031") + Decimal(index) / Decimal("1000")),
            Decimal("1000") + Decimal(offset),
        )
        for index, key in enumerate(active_keys)
        for offset in range(505)
    )
    dividends = tuple(
        Dividend(
            key,
            date(2024, month, 1),
            f"{key.code}-div-{month}",
            Decimal("0.20") + Decimal(index) / Decimal("100"),
            "EUR",
        )
        for index, key in enumerate(active_keys)
        for month in range(1, 13)
    )
    splits = (
        Split(active_keys[0], date(2024, 6, 1), "2:1", Decimal("2")),
        Split(active_keys[1], date(2024, 6, 1), "3:2", Decimal("1.5")),
    )
    return ImmutableGateway(
        active,
        MarketDataSnapshot(active + (inactive,), quotes, dividends, splits),
    )


def _metadata_service(state: HostedApiState, gateway: ImmutableGateway) -> MetadataProjectService:
    return MetadataProjectService(
        state,
        LocalHostedRuntime(
            quote_workflow=_empty_workflow, metadata_workflow=_empty_workflow, cpu_count=lambda: 1
        ),
        LocalProjectRepository(state),
        LocalSelectionRepository(state),
        LocalMetadataLifecycleRepository(state),
        state.credential_vault(),
        LocalAuditEventRepository(state),
        market_catalog=lambda: metadata_source_catalog(gateway),  # type: ignore[arg-type]
    )


def _research_services(
    state: HostedApiState, gateway: ImmutableGateway
) -> tuple[
    MarketSourceUnivariateResearchService,
    MarketSourceBivariateResearchService,
    MarketSourceMultivariateResearchService,
]:
    repository = HostedResearchRepository(state)
    persistence = LocalResearchPersistence(state)
    data = MarketSourceResearchData(gateway)
    return (
        MarketSourceUnivariateResearchService(repository, data, persistence),
        MarketSourceBivariateResearchService(
            repository, BivariateMarketSourceData(gateway), persistence
        ),
        MarketSourceMultivariateResearchService(
            data,
            persistence,
            repository,
            LocalProjectRepository(state),
            LocalSelectionRepository(state),
            LocalMultivariateRunRepository(state),
            lambda: tuple(
                {
                    "isin": listing.key.isin,
                    "exchange": listing.key.exchange,
                    "code": listing.key.code,
                    "instrument_type": listing.instrument_type,
                }
                for listing in gateway.active
            ),
            lambda: 1,
            None,
        ),
    )


def test_four_stage_market_source_contract_has_full_identity_and_one_lineage() -> None:
    """Run every analytical stage from immutable market rows, end to end."""
    user_id = "qa-user"
    state = HostedApiState()
    gateway = _fixture()
    source_before = gateway.snapshot
    metadata = _metadata_service(state, gateway)

    fetched, _ = metadata.start_metadata_fetch(user_id)
    project = metadata.create_project_from_criteria(
        user_id,
        exchange="XETRA",
        name="Monthly",
        instrument_type="ETF",
        country="IE",
        currency="EUR",
        idempotency_key=None,
    )
    metadata_selection = project["selection"]
    assert metadata_selection["member_ids"] == [
        "IE00QA000001:XETRA:QA-A",
        "IE00QA000001:XETRA:QA-B",
        "IE00QA000003:XETRA:QA-C",
        "IE00QA000004:XETRA:QA-D",
        "IE00QA000005:XETRA:QA-E",
    ]
    assert fetched["snapshot_id"] == state.metadata_revisions_by_user[user_id]
    assert "IE00INACTIVE:XETRA:OLD" not in metadata_selection["member_ids"]

    univariate, bivariate, multivariate = _research_services(state, gateway)
    metadata_selection_id = str(metadata_selection["selection_id"])
    univariate_started = univariate.start(user_id, metadata_selection_id)
    univariate.complete(user_id, metadata_selection_id)
    univariate_run = state.univariate_runs_by_id[str(univariate_started["run_id"])]
    current_selection_id = state.current_univariate_selection_by_user[user_id]
    assert univariate_run.status == "complete"
    assert len(univariate_run.rows) == 5
    assert univariate_run.source_id

    bivariate_started = bivariate.start(user_id, current_selection_id)
    bivariate.complete(user_id, current_selection_id)
    bivariate_run = state.bivariate_runs_by_id[str(bivariate_started["run_id"])]
    assert bivariate_run.status == "complete"
    # Both listing identities survive Metadata/Univariate.  Pair construction
    # intentionally omits the same-underlying (same ISIN) relation, leaving 9
    # valid cross-underlying pairs rather than collapsing either listing.
    assert bivariate_run.total == 9

    multivariate_started = multivariate.start(
        user_id,
        str(project["project"]["project_id"]),
        bivariate_run.run_id,
        {},
    )
    multivariate_run = state.multivariate_runs_by_id[str(multivariate_started["run_id"])]
    with ThreadPoolExecutor(max_workers=1) as executor:
        computed = multivariate._compute(  # pyright: ignore[reportPrivateUsage]
            multivariate_run, executor=executor, on_phase=lambda *_args: None
        )

    snapshot_id = (
        MarketSourceResearchData(gateway).read(tuple(metadata_selection["member_ids"])).snapshot_id
    )
    assert snapshot_id.startswith("market_source_snapshot_")
    assert bivariate_run.source_id.endswith(snapshot_id)
    assert computed.summary["market_source_snapshot_id"] == snapshot_id
    assert computed.artifacts["market_source"]["snapshot_id"] == snapshot_id
    assert len(computed.candidates) > 0
    # Decimal/date source fields are projected once, without split-adjusting prices.
    projected = MarketSourceResearchData(gateway).read(tuple(metadata_selection["member_ids"]))
    assert projected.quotes[0]["date"] == "2023-01-03"
    assert projected.quotes[0]["adjusted_close"] == 100.0
    assert projected.dividends[0]["amount"] == 0.2
    assert projected.splits[0]["split_factor"] == 2.0
    # Corporate actions are carried as lineage/input evidence.  They do not
    # alter quote projection or Bivariate return calculations behind the back
    # of the frozen adjusted-close source policy.
    action_free = ImmutableGateway(
        gateway.active,
        MarketDataSnapshot(gateway.active, gateway.snapshot.quotes, (), ()),
    )
    assert (
        BivariateMarketSourceData(gateway).read(tuple(metadata_selection["member_ids"])).quotes
        == BivariateMarketSourceData(action_free)
        .read(tuple(metadata_selection["member_ids"]))
        .quotes
    )
    assert source_before == gateway.snapshot  # all four stages are strictly read-only
    assert gateway.snapshot_reads >= 6


def test_four_stage_market_source_fails_closed_for_missing_adjusted_close() -> None:
    """A partial source row cannot silently fall back to raw close or local data."""
    state = HostedApiState()
    gateway = _fixture(missing_adjusted=True)
    metadata = _metadata_service(state, gateway)
    project = metadata.create_project_from_criteria(
        "qa-user",
        exchange="XETRA",
        name="Monthly",
        instrument_type="ETF",
        country="IE",
        currency="EUR",
        idempotency_key=None,
    )
    univariate, _, _ = _research_services(state, gateway)

    with pytest.raises(HostedApplicationError, match=MISSING_ADJUSTED_CLOSE):
        univariate.start("qa-user", str(project["selection"]["selection_id"]))


def test_bivariate_fails_closed_when_the_source_has_no_common_return_history() -> None:
    """A present-but-insufficient source must not produce zero-valued pair statistics."""
    user_id = "qa-user"
    state = HostedApiState()
    gateway = _fixture()
    # Each selected full identity exists, but there is no return interval.
    gateway.snapshot = MarketDataSnapshot(
        gateway.snapshot.listings,
        tuple(quote for quote in gateway.snapshot.quotes if quote.trade_date == date(2023, 1, 3)),
        gateway.snapshot.dividends,
        gateway.snapshot.splits,
    )
    metadata = _metadata_service(state, gateway)
    project = metadata.create_project_from_criteria(
        user_id,
        exchange="XETRA",
        name="Monthly",
        instrument_type="ETF",
        country="IE",
        currency="EUR",
        idempotency_key=None,
    )
    univariate, bivariate, _ = _research_services(state, gateway)
    selection_id = str(project["selection"]["selection_id"])
    started = univariate.start(user_id, selection_id)
    univariate.complete(user_id, selection_id)
    assert state.univariate_runs_by_id[str(started["run_id"])].status == "complete"
    univariate_selection_id = state.current_univariate_selection_by_user[user_id]
    bivariate_started = bivariate.start(user_id, univariate_selection_id)
    bivariate.complete(user_id, univariate_selection_id)

    failed = state.bivariate_runs_by_id[str(bivariate_started["run_id"])]
    assert failed.status == "failed"
    assert failed.rows == ()
