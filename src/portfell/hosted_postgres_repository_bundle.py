"""One explicit PostgreSQL repository bundle for hosted runtime composition."""

from __future__ import annotations

from dataclasses import dataclass

from portfell.hosted_analysis_record_repository import PostgresAnalysisRecordRepository
from portfell.hosted_audit_event_repository import PostgresAuditEventRepository
from portfell.hosted_idempotency_repository import PostgresIdempotencyRepository
from portfell.hosted_metadata_repository import PostgresMetadataLifecycleRepository
from portfell.hosted_multivariate_run_repository import PostgresMultivariateRunRepository
from portfell.hosted_navigation_read_model_repository import PostgresNavigationReadModel
from portfell.hosted_project_settings_repository import PostgresProjectSettingsRepository
from portfell.hosted_repository_importer import PostgresProjectRepository
from portfell.hosted_selection_repository import PostgresSelectionRepository


@dataclass(frozen=True)
class PostgresHostedRepositoryBundle:
    """Transitional analytical repositories sharing one workspace connection.

    The production bundle intentionally contains no hosted-user, tenant-membership, project-
    membership, or provider-credential repository. Legacy database objects may remain until the
    destructive database replacement wave, but they are no longer runtime authorities here.
    """

    projects: PostgresProjectRepository
    selections: PostgresSelectionRepository
    metadata: PostgresMetadataLifecycleRepository
    idempotency: PostgresIdempotencyRepository
    audit: PostgresAuditEventRepository
    settings: PostgresProjectSettingsRepository
    multivariate: PostgresMultivariateRunRepository
    navigation: PostgresNavigationReadModel
    analyses: PostgresAnalysisRecordRepository

    @classmethod
    def from_connection(cls, connection: object) -> PostgresHostedRepositoryBundle:
        """Compose adapters without opening a second connection or transaction."""

        return cls(
            projects=PostgresProjectRepository(connection),  # type: ignore[arg-type]
            selections=PostgresSelectionRepository(connection),  # type: ignore[arg-type]
            metadata=PostgresMetadataLifecycleRepository(connection),  # type: ignore[arg-type]
            idempotency=PostgresIdempotencyRepository(connection),  # type: ignore[arg-type]
            audit=PostgresAuditEventRepository(connection),  # type: ignore[arg-type]
            settings=PostgresProjectSettingsRepository(connection),  # type: ignore[arg-type]
            multivariate=PostgresMultivariateRunRepository(connection),  # type: ignore[arg-type]
            navigation=PostgresNavigationReadModel(connection),  # type: ignore[arg-type]
            analyses=PostgresAnalysisRecordRepository(connection),  # type: ignore[arg-type]
        )
