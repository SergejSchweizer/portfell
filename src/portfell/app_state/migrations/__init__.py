"""Forward-only migration declarations for the clean app-state database."""

from portfell.app_state.migrations.v001_initial import MIGRATION_V001
from portfell.app_state.migrations.v002_analysis_jobs import MIGRATION_V002
from portfell.app_state.migrations.v003_analysis_artifact_items import MIGRATION_V003
from portfell.app_state.migrations.v004_module_ownership import MIGRATION_V004
from portfell.app_state.migrations.v005_workflow_leases import MIGRATION_V005
from portfell.app_state.migrations.v006_module_roles import MIGRATION_V006
from portfell.app_state.migrations.v007_multivariate_checkpoints import MIGRATION_V007
from portfell.app_state.migrations.v008_resume_artifact_dedup import MIGRATION_V008

__all__ = [
    "MIGRATION_V001",
    "MIGRATION_V002",
    "MIGRATION_V003",
    "MIGRATION_V004",
    "MIGRATION_V005",
    "MIGRATION_V006",
    "MIGRATION_V007",
    "MIGRATION_V008",
]
