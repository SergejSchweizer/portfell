"""Clean single-workspace application-state database contracts."""

from portfell.app_state.config import APP_DATABASE_NAME, APP_SCHEMA_NAME, validate_app_state_config
from portfell.app_state.contracts import (
    AnalysisArtifactRecord,
    AnalysisJobRecord,
    AnalysisRunRecord,
    DecisionArtifactRecord,
    ListingIdentity,
    MarketSourceSnapshotRecord,
    MetadataUniverseRecord,
    UiPreferenceRecord,
    UnivariateSelectionRecord,
)
from portfell.app_state.migration import (
    APP_STATE_MIGRATIONS,
    catalog_fingerprint,
    migrate_to_head,
    rollback_to_zero,
)
from portfell.app_state.repository import PostgresAppStateRepository
from portfell.app_state.schema import (
    ANALYSIS_STAGES,
    ANALYSIS_STATUSES,
    APP_STATE_TABLES,
    MULTIVARIATE_OBJECTIVES,
)

__all__ = [
    "ANALYSIS_STAGES",
    "ANALYSIS_STATUSES",
    "APP_DATABASE_NAME",
    "APP_SCHEMA_NAME",
    "APP_STATE_MIGRATIONS",
    "APP_STATE_TABLES",
    "MULTIVARIATE_OBJECTIVES",
    "AnalysisArtifactRecord",
    "AnalysisJobRecord",
    "AnalysisRunRecord",
    "DecisionArtifactRecord",
    "ListingIdentity",
    "MarketSourceSnapshotRecord",
    "MetadataUniverseRecord",
    "PostgresAppStateRepository",
    "UiPreferenceRecord",
    "UnivariateSelectionRecord",
    "catalog_fingerprint",
    "migrate_to_head",
    "rollback_to_zero",
    "validate_app_state_config",
]
