"""One explicit PostgreSQL repository bundle for hosted runtime composition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from portfell.hosted_analysis_record_repository import PostgresAnalysisRecordRepository
from portfell.hosted_audit_event_repository import PostgresAuditEventRepository
from portfell.hosted_credentials import PostgresCredentialStore
from portfell.hosted_idempotency_repository import PostgresIdempotencyRepository
from portfell.hosted_metadata_repository import PostgresMetadataLifecycleRepository
from portfell.hosted_multivariate_run_repository import PostgresMultivariateRunRepository
from portfell.hosted_navigation_read_model_repository import PostgresNavigationReadModel
from portfell.hosted_project_settings_repository import PostgresProjectSettingsRepository
from portfell.hosted_quote_lifecycle_repository import PostgresQuoteLifecycleRepository
from portfell.hosted_repository_importer import PostgresProjectRepository
from portfell.hosted_selection_repository import PostgresSelectionRepository
from portfell.hosted_user_repository import PostgresHostedUserRepository


@dataclass(frozen=True)
class PostgresHostedRepositoryBundle:
    """All control-plane repositories sharing one request-scoped connection."""

    users: PostgresHostedUserRepository
    credentials: PostgresCredentialStore
    projects: PostgresProjectRepository
    selections: PostgresSelectionRepository
    metadata: PostgresMetadataLifecycleRepository
    quotes: PostgresQuoteLifecycleRepository
    idempotency: PostgresIdempotencyRepository
    audit: PostgresAuditEventRepository
    settings: PostgresProjectSettingsRepository
    multivariate: PostgresMultivariateRunRepository
    navigation: PostgresNavigationReadModel
    analyses: PostgresAnalysisRecordRepository

    @classmethod
    def from_connection(
        cls,
        connection: object,
        *,
        navigation_refresher: Callable[[str], object] | None = None,
    ) -> PostgresHostedRepositoryBundle:
        """Compose adapters without opening a second connection or transaction."""

        return cls(
            users=PostgresHostedUserRepository(connection),  # type: ignore[arg-type]
            credentials=PostgresCredentialStore(connection),  # type: ignore[arg-type]
            projects=PostgresProjectRepository(connection),  # type: ignore[arg-type]
            selections=PostgresSelectionRepository(connection),  # type: ignore[arg-type]
            metadata=PostgresMetadataLifecycleRepository(
                connection,  # type: ignore[arg-type]
                navigation_refresher=navigation_refresher,
            ),
            quotes=PostgresQuoteLifecycleRepository(connection),  # type: ignore[arg-type]
            idempotency=PostgresIdempotencyRepository(connection),  # type: ignore[arg-type]
            audit=PostgresAuditEventRepository(connection),  # type: ignore[arg-type]
            settings=PostgresProjectSettingsRepository(connection),  # type: ignore[arg-type]
            multivariate=PostgresMultivariateRunRepository(connection),  # type: ignore[arg-type]
            navigation=PostgresNavigationReadModel(connection),  # type: ignore[arg-type]
            analyses=PostgresAnalysisRecordRepository(connection),  # type: ignore[arg-type]
        )
