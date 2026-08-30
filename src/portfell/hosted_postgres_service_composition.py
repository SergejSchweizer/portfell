"""PostgreSQL/shared-market service composition for the hosted API factory."""

from __future__ import annotations

from portfell.hosted_analysis_service import HostedAnalysisService
from portfell.hosted_api_state import HostedApiState
from portfell.hosted_credential_project_service import CredentialProjectService
from portfell.hosted_market_source_bivariate_service import (
    BivariateMarketSourceData,
    MarketSourceBivariateResearchService,
)
from portfell.hosted_market_source_multivariate_service import (
    MarketSourceMultivariateResearchService,
)
from portfell.hosted_market_source_research_data import MarketSourceResearchData
from portfell.hosted_market_source_research_repository import MarketSourcePostgresResearchRepository
from portfell.hosted_market_source_univariate_service import MarketSourceUnivariateResearchService
from portfell.hosted_metadata_project_service import MetadataProjectService, metadata_source_catalog
from portfell.hosted_postgres_repository_bundle import PostgresHostedRepositoryBundle
from portfell.hosted_postgres_request_scope import RequestScopedPostgresConnection
from portfell.hosted_postgres_runtime import PostgresHostedRuntime
from portfell.hosted_postgres_workflow import PostgresWorkflowReader
from portfell.hosted_research_persistence import PostgresResearchPersistence
from portfell.hosted_research_service import ResearchService
from portfell.market_source.gateway import MarketDataGateway


def build_postgres_services(
    state: HostedApiState,
    *,
    request_scope: RequestScopedPostgresConnection,
    market_gateway: MarketDataGateway | None = None,
) -> tuple[CredentialProjectService, MetadataProjectService, ResearchService]:
    """Compose services with PostgreSQL control records and external market reads."""

    repositories = PostgresHostedRepositoryBundle.from_connection(request_scope)
    runtime = PostgresHostedRuntime(market_gateway=market_gateway)
    bivariate_data = BivariateMarketSourceData(runtime.market_gateway)
    market_data = MarketSourceResearchData(runtime.market_gateway)

    def project_active_run(user_id: str, project_id: str) -> dict[str, object] | None:
        selection = repositories.selections.for_project(project_id=project_id, user_id=user_id)
        if selection is None:
            return None
        research = research_repository.workflow_state(
            user_id=user_id,
            project_id=project_id,
            metadata_selection_id=selection.selection_id,
        )
        if research.multivariate_status == "running":
            return {"status": "running"}
        if research.bivariate_status == "running":
            return {"status": "running"}
        if research.univariate_status == "running":
            return {"status": "running"}
        return None

    research_repository = MarketSourcePostgresResearchRepository(
        request_scope,
        projects=repositories.projects,
        selections=repositories.selections,
        analyses=repositories.analyses,
    )
    workflow_reader = PostgresWorkflowReader(
        selections=repositories.selections,
        metadata_rows=runtime.all_isins_rows,
        research_state=(
            lambda user_id, project_id, metadata_selection_id: research_repository.workflow_state(
                user_id=user_id,
                project_id=project_id,
                metadata_selection_id=metadata_selection_id,
            )
        ),
    )
    persistence = PostgresResearchPersistence()
    credentials = CredentialProjectService(
        state,
        runtime,
        repositories.projects,
        repositories.selections,
        repositories.settings,
        repositories.audit,
        repositories.idempotency,
        workflow_reader,
        lambda _user_id, _project_id: True,
        project_active_run,
        repositories.navigation.read,
        repositories.navigation.write,
    )
    metadata = MetadataProjectService(
        state,
        runtime,
        repositories.projects,
        repositories.selections,
        repositories.metadata,
        repositories.audit,
        credentials.refresh_navigation,
        lambda: metadata_source_catalog(runtime.market_gateway),
    )
    research = ResearchService(
        MarketSourceUnivariateResearchService(research_repository, market_data, persistence),
        MarketSourceBivariateResearchService(research_repository, bivariate_data, persistence),
        MarketSourceMultivariateResearchService(
            market_data,
            persistence,
            research_repository,
            repositories.projects,
            repositories.selections,
            repositories.multivariate,
            runtime.all_isins_rows,
            runtime.process_cpu_count,
            None,
        ),
        HostedAnalysisService(research_repository, persistence),
    )
    return credentials, metadata, research
