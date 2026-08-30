"""Explicit local adapters retained for unit tests and CLI compatibility only."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Never, cast

from portfell.hosted_analysis_service import HostedAnalysisService
from portfell.hosted_api_local_runtime import LocalHostedRuntime
from portfell.hosted_api_ports import Workflow
from portfell.hosted_api_service_support import project_data_loaded, workflow_row
from portfell.hosted_api_state import HostedApiState
from portfell.hosted_credential_project_service import CredentialProjectService
from portfell.hosted_credentials import FileCredentialStore, KeyEncryptionKey
from portfell.hosted_idempotency_repository import LocalIdempotencyRepository
from portfell.hosted_local_audit_event_repository import LocalAuditEventRepository
from portfell.hosted_local_metadata_repository import LocalMetadataLifecycleRepository
from portfell.hosted_local_project_repository import LocalProjectRepository
from portfell.hosted_local_selection_repository import LocalSelectionRepository
from portfell.hosted_market_source_bivariate_service import (
    BivariateMarketSourceData,
    MarketSourceBivariateResearchService,
)
from portfell.hosted_market_source_research_data import MarketSourceResearchData
from portfell.hosted_market_source_univariate_service import MarketSourceUnivariateResearchService
from portfell.hosted_metadata_project_service import MetadataProjectService
from portfell.hosted_multivariate_run_repository import LocalMultivariateRunRepository
from portfell.hosted_multivariate_service import MultivariateResearchService
from portfell.hosted_project_settings_repository import LocalProjectSettingsRepository
from portfell.hosted_research_persistence import LocalResearchPersistence
from portfell.hosted_research_ports import ResearchDataPort
from portfell.hosted_research_repository import HostedResearchRepository
from portfell.hosted_research_service import ResearchService
from portfell.hosted_univariate_service import UnivariateResearchService
from portfell.hosted_workspace import LocalWorkspaceStore
from portfell.hosted_workspace_repository import restore_local_workspace
from portfell.market_source.errors import market_source_required
from portfell.market_source.gateway import MarketDataGateway


def _retired_market_acquisition(**_: object) -> Never:
    """Keep legacy lifecycle wiring non-executable until its owner is deleted."""

    market_source_required()


def local_runtime() -> LocalHostedRuntime:
    return LocalHostedRuntime(
        quote_workflow=cast(Workflow, _retired_market_acquisition),
        metadata_workflow=cast(Workflow, _retired_market_acquisition),
        cpu_count=lambda: os.process_cpu_count(),
    )


def local_research_service(
    state: HostedApiState,
    data: ResearchDataPort,
    *,
    market_gateway: MarketDataGateway | None = None,
) -> ResearchService:
    repository = HostedResearchRepository(state)
    persistence = LocalResearchPersistence(state)
    univariate = (
        UnivariateResearchService(repository, data, persistence)
        if market_gateway is None
        else MarketSourceUnivariateResearchService(
            repository, MarketSourceResearchData(market_gateway), persistence
        )
    )
    return ResearchService(
        univariate,
        MarketSourceBivariateResearchService(
            repository,
            BivariateMarketSourceData(cast(MarketDataGateway, market_gateway)),
            persistence,
        ),
        MultivariateResearchService(
            data,
            persistence,
            repository,
            LocalProjectRepository(state),
            LocalSelectionRepository(state),
            LocalMultivariateRunRepository(state),
            lambda: state.all_isins_rows,
            lambda: os.process_cpu_count(),
            None,
        ),
        HostedAnalysisService(repository, persistence),
    )


def local_credential_project_service(state: HostedApiState) -> CredentialProjectService:
    """Compose every local credential-service port explicitly."""

    return CredentialProjectService(
        state,
        runtime=local_runtime(),
        project_repository=LocalProjectRepository(state),
        selection_repository=LocalSelectionRepository(state),
        project_settings_repository=LocalProjectSettingsRepository(state),
        credential_vault=state.credential_vault(),
        audit_repository=LocalAuditEventRepository(state),
        idempotency_repository=LocalIdempotencyRepository(state),
        workflow_reader=lambda user_id, project_id: workflow_row(state, user_id, project_id),
        project_data_loaded_reader=lambda user_id, project_id: project_data_loaded(
            state, project_id, user_id
        ),
        navigation_reader=lambda _user_id: None,
        navigation_writer=lambda _user_id, payload: (payload, ""),
    )


def local_test_services(
    state: HostedApiState, *, market_gateway: MarketDataGateway | None = None
) -> tuple[CredentialProjectService, MetadataProjectService, ResearchService]:
    """Compose non-production adapters for explicit API tests only."""

    runtime = local_runtime()
    return (
        local_credential_project_service(state),
        MetadataProjectService(
            state,
            runtime,
            LocalProjectRepository(state),
            LocalSelectionRepository(state),
            LocalMetadataLifecycleRepository(state),
            state.credential_vault(),
            LocalAuditEventRepository(state),
        ),
        local_research_service(state, runtime, market_gateway=market_gateway),
    )


def create_persistent_local_workspace_state(
    shared_data_root: Path, *, key_encryption_key: KeyEncryptionKey
) -> HostedApiState:
    workspace_store = LocalWorkspaceStore(shared_data_root / "local-workspace.json")
    state = HostedApiState(
        credentials=FileCredentialStore(shared_data_root / "encrypted-credentials.json"),
        credential_key_encryption_key=key_encryption_key,
        workspace_store=workspace_store,
    )
    restore_local_workspace(state, workspace_store.load())
    return state
