"""Test-only composition for hosted API route and contract tests.

It deliberately contains no filesystem, provider, credential, or local market
runtime. Market-backed tests inject an immutable gateway fixture explicitly.
"""

from __future__ import annotations

from typing import cast

from portfell.hosted_analysis_service import HostedAnalysisService
from portfell.hosted_api_state import HostedApiState
from portfell.hosted_credential_project_service import CredentialProjectService
from portfell.hosted_idempotency_repository import LocalIdempotencyRepository
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
from portfell.hosted_metadata_project_service import MetadataProjectService
from portfell.hosted_multivariate_run_repository import LocalMultivariateRunRepository
from portfell.hosted_multivariate_service import MultivariateResearchService
from portfell.hosted_project_settings_repository import LocalProjectSettingsRepository
from portfell.hosted_research_persistence import LocalResearchPersistence
from portfell.hosted_research_ports import ResearchDataPort, ResearchDataset, UnivariateProgress
from portfell.hosted_research_repository import HostedResearchRepository
from portfell.hosted_research_service import ResearchService
from portfell.hosted_univariate_service import UnivariateResearchService
from portfell.market_source.gateway import MarketDataGateway
from portfell.table_io import JsonRow


class InMemoryRuntime:
    """In-memory hosted runtime substitute limited to non-market test state."""

    def __init__(self, state: HostedApiState) -> None:
        self._state = state

    def all_isins_rows(self) -> tuple[JsonRow, ...]:
        return self._state.all_isins_rows

    def process_cpu_count(self) -> int:
        return 1


class EmptyResearchData:
    """Fail-closed test data port for routes that do not request market data."""

    def has_selected_rows(self, member_ids: tuple[str, ...], *, dataset: ResearchDataset) -> bool:
        del member_ids, dataset
        return False

    def selected_rows(
        self, member_ids: tuple[str, ...], *, dataset: ResearchDataset
    ) -> tuple[JsonRow, ...]:
        del member_ids, dataset
        return ()

    def build_univariate_rows(
        self,
        member_ids: tuple[str, ...],
        *,
        on_progress: UnivariateProgress | None = None,
    ) -> tuple[JsonRow, ...]:
        for completed in range(1, len(member_ids) + 1):
            if on_progress is not None:
                on_progress(completed)
        return ()


def build_research_service(
    state: HostedApiState, *, market_gateway: MarketDataGateway | None = None
) -> ResearchService:
    """Build a test-only research service; market reads require explicit injection."""

    repository = HostedResearchRepository(state)
    persistence = LocalResearchPersistence(state)
    data: ResearchDataPort = (
        EmptyResearchData() if market_gateway is None else MarketSourceResearchData(market_gateway)
    )
    univariate = (
        UnivariateResearchService(repository, data, persistence)
        if market_gateway is None
        else MarketSourceUnivariateResearchService(repository, data, persistence)
    )
    return ResearchService(
        univariate,
        MarketSourceBivariateResearchService(
            repository,
            BivariateMarketSourceData(cast(MarketDataGateway, market_gateway)),
            persistence,
        ),
        (
            MultivariateResearchService(
                data,
                persistence,
                repository,
                LocalProjectRepository(state),
                LocalSelectionRepository(state),
                LocalMultivariateRunRepository(state),
                lambda: state.all_isins_rows,
                lambda: 1,
                None,
            )
            if market_gateway is None
            else MarketSourceMultivariateResearchService(
                data,
                persistence,
                repository,
                LocalProjectRepository(state),
                LocalSelectionRepository(state),
                LocalMultivariateRunRepository(state),
                lambda: state.all_isins_rows,
                lambda: 1,
                None,
            )
        ),
        HostedAnalysisService(repository, persistence),
    )


def build_services(
    state: HostedApiState, *, market_gateway: MarketDataGateway | None = None
) -> tuple[CredentialProjectService, MetadataProjectService, ResearchService]:
    """Build explicit non-production services for HTTP contract tests."""

    runtime = InMemoryRuntime(state)
    return (
        CredentialProjectService(
            state,
            runtime=runtime,
            project_repository=LocalProjectRepository(state),
            selection_repository=LocalSelectionRepository(state),
            project_settings_repository=LocalProjectSettingsRepository(state),
            audit_repository=LocalAuditEventRepository(state),
            idempotency_repository=LocalIdempotencyRepository(state),
        ),
        MetadataProjectService(
            state,
            runtime,
            LocalProjectRepository(state),
            LocalSelectionRepository(state),
            LocalMetadataLifecycleRepository(state),
            LocalAuditEventRepository(state),
        ),
        build_research_service(state, market_gateway=market_gateway),
    )
