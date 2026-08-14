"""PostgreSQL/shared-market service composition for the hosted API factory."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from portfell.hosted_analysis_service import HostedAnalysisService
from portfell.hosted_api_state import HostedApiState
from portfell.hosted_bivariate_service import BivariateResearchService
from portfell.hosted_credential_project_service import CredentialProjectService
from portfell.hosted_credentials import EodhdCredentialVault, KeyEncryptionKey
from portfell.hosted_download_run_repository import PostgresDownloadRunRepository
from portfell.hosted_metadata_project_service import MetadataProjectService
from portfell.hosted_metadata_refresh_job_repository import PostgresMetadataRefreshJobRepository
from portfell.hosted_multivariate_service import MultivariateResearchService
from portfell.hosted_navigation_reconciler import PostgresNavigationReconciler
from portfell.hosted_postgres_repository_bundle import PostgresHostedRepositoryBundle
from portfell.hosted_postgres_request_scope import RequestScopedPostgresConnection
from portfell.hosted_postgres_research_repository import PostgresResearchRepository
from portfell.hosted_postgres_runtime import PostgresHostedRuntime
from portfell.hosted_postgres_workflow import PostgresWorkflowReader
from portfell.hosted_project_bootstrap_repository import PostgresProjectBootstrapRepository
from portfell.hosted_quote_run_service import QuoteRunService
from portfell.hosted_research_persistence import PostgresResearchPersistence
from portfell.hosted_research_service import ResearchService
from portfell.hosted_shared_market_research_data import SharedMarketResearchData
from portfell.hosted_shared_quote_publisher import SharedQuotePublisher
from portfell.hosted_univariate_service import UnivariateResearchService
from portfell.shared_market_data import SharedMarketDataStore


def build_postgres_services(
    state: HostedApiState,
    *,
    request_scope: RequestScopedPostgresConnection,
    shared_data_root: Path,
    key_encryption_key: KeyEncryptionKey,
) -> tuple[CredentialProjectService, MetadataProjectService, QuoteRunService, ResearchService]:
    """Compose services with PostgreSQL control records and shared payloads only."""

    navigation_reconciler = PostgresNavigationReconciler(request_scope)
    repositories = PostgresHostedRepositoryBundle.from_connection(
        request_scope, navigation_refresher=navigation_reconciler.reconcile
    )
    credential_vault = EodhdCredentialVault(
        store=repositories.credentials,
        key_encryption_key=key_encryption_key,
        fingerprint_secret=key_encryption_key.material,
    )
    runtime = PostgresHostedRuntime(shared_data_root)
    shared_store = SharedMarketDataStore(shared_data_root)
    data = SharedMarketResearchData(shared_store)
    bootstrap = PostgresProjectBootstrapRepository(request_scope)

    def project_data_loaded(user_id: str, project_id: str) -> bool:
        fill = bootstrap.status(user_id=user_id, project_id=project_id)
        return fill is not None and fill.status == "ready"

    def project_active_run(user_id: str, project_id: str) -> dict[str, object] | None:
        fill = bootstrap.status(user_id=user_id, project_id=project_id)
        if fill is not None and fill.status in {"planning", "running"}:
            return {"status": "waiting" if fill.status == "planning" else "running"}
        if fill is None or fill.status != "ready":
            return None
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

    def quote_rows(run_id: str) -> tuple[dict[str, object], ...]:
        row = request_scope.execute(
            "select response_manifest from portfell_app.download_runs "
            "where download_run_id = %s::uuid",
            (run_id,),
        ).fetchone()
        if row is None or len(row) != 1 or not isinstance(row[0], dict):
            return ()
        manifest = cast(dict[str, object], row[0])
        scope = cast(object, manifest.get("requested_scope"))
        if not isinstance(scope, dict):
            return ()
        members = cast(object, cast(dict[str, object], scope).get("member_ids"))
        if not isinstance(members, list):
            return ()
        typed_members = cast(list[object], members)
        if not all(isinstance(item, str) for item in typed_members):
            return ()
        return data.selected_rows(tuple(cast(list[str], typed_members)), dataset="quotes")

    research_repository = PostgresResearchRepository(
        request_scope,
        projects=repositories.projects,
        selections=repositories.selections,
        quotes=repositories.quotes,
        quote_rows=quote_rows,
        analyses=repositories.analyses,
    )
    workflow_reader = PostgresWorkflowReader(
        selections=repositories.selections,
        bootstrap=bootstrap,
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
        credential_vault,
        repositories.audit,
        PostgresDownloadRunRepository(request_scope),
        repositories.idempotency,
        workflow_reader,
        project_data_loaded,
        project_active_run,
        repositories.navigation.read,
        repositories.navigation.write,
        navigation_reconciler.reconcile,
    )
    metadata = MetadataProjectService(
        state,
        runtime,
        repositories.projects,
        repositories.selections,
        repositories.metadata,
        credential_vault,
        repositories.audit,
        bootstrap,
        PostgresMetadataRefreshJobRepository(request_scope),
        credentials.refresh_navigation,
    )
    quotes = QuoteRunService(
        state,
        runtime,
        repositories.projects,
        repositories.selections,
        credential_vault,
        repositories.quotes,
        repositories.audit,
        repositories.idempotency,
        SharedQuotePublisher(shared_store),
    )
    research = ResearchService(
        UnivariateResearchService(research_repository, data, persistence),
        BivariateResearchService(research_repository, data, persistence),
        MultivariateResearchService(
            state,
            data,
            persistence,
            research_repository,
            repositories.projects,
            repositories.selections,
            repositories.multivariate,
            runtime.all_isins_rows,
            runtime.process_cpu_count,
        ),
        HostedAnalysisService(research_repository, persistence),
    )
    return credentials, metadata, quotes, research
