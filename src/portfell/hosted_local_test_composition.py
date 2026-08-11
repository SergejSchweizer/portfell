"""Explicit local adapters retained for unit tests and CLI compatibility only."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

from portfell.hosted_analysis_service import HostedAnalysisService
from portfell.hosted_api_local_runtime import LocalHostedRuntime
from portfell.hosted_api_ports import Workflow
from portfell.hosted_api_state import HostedApiState
from portfell.hosted_bivariate_service import BivariateResearchService
from portfell.hosted_credentials import FileCredentialStore, KeyEncryptionKey
from portfell.hosted_multivariate_service import MultivariateResearchService
from portfell.hosted_research_persistence import LocalResearchPersistence
from portfell.hosted_research_ports import ResearchDataPort
from portfell.hosted_research_repository import HostedResearchRepository
from portfell.hosted_research_service import ResearchService
from portfell.hosted_univariate_service import UnivariateResearchService
from portfell.hosted_workspace import LocalWorkspaceStore
from portfell.hosted_workspace_repository import restore_local_workspace
from portfell.shared_market_data import SharedMarketDataStore
from portfell.workflows import run_fetch_all_metadata_workflow, run_fetch_all_quotes_workflow


def local_runtime() -> LocalHostedRuntime:
    return LocalHostedRuntime(
        quote_workflow=cast(Workflow, run_fetch_all_quotes_workflow),
        metadata_workflow=cast(Workflow, run_fetch_all_metadata_workflow),
        cpu_count=lambda: os.process_cpu_count(),
    )


def local_research_service(state: HostedApiState, data: ResearchDataPort) -> ResearchService:
    repository = HostedResearchRepository(state)
    persistence = LocalResearchPersistence(state)
    return ResearchService(
        UnivariateResearchService(repository, data, persistence),
        BivariateResearchService(repository, data, persistence),
        MultivariateResearchService(state, data, persistence, repository),
        HostedAnalysisService(repository, persistence),
    )


def create_persistent_local_workspace_state(
    shared_data_root: Path, *, key_encryption_key: KeyEncryptionKey
) -> HostedApiState:
    workspace_store = LocalWorkspaceStore(shared_data_root / "local-workspace.json")
    state = HostedApiState(
        credentials=FileCredentialStore(shared_data_root / "encrypted-credentials.json"),
        credential_key_encryption_key=key_encryption_key,
        workspace_store=workspace_store,
        shared_market_data_store=SharedMarketDataStore(shared_data_root),
    )
    restore_local_workspace(state, workspace_store.load())
    return state


def run_quote_fetch_for_test(
    state: HostedApiState, run: Any, selection_id: str, provider_key: str
) -> None:
    from portfell.hosted_quote_run_service import QuoteRunService

    QuoteRunService(state, local_runtime()).run_quote_fetch(run, selection_id, provider_key)
