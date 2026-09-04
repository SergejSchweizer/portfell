"""Forward-only migration declarations for the clean app-state database."""

from portfell.app_state.migrations.v001_initial import MIGRATION_V001
from portfell.app_state.migrations.v002_analysis_jobs import MIGRATION_V002
from portfell.app_state.migrations.v003_analysis_artifact_items import MIGRATION_V003
from portfell.app_state.migrations.v004_module_ownership import MIGRATION_V004
from portfell.app_state.migrations.v005_workflow_leases import MIGRATION_V005
from portfell.app_state.migrations.v006_module_roles import MIGRATION_V006

__all__ = [
    "MIGRATION_V001",
    "MIGRATION_V002",
    "MIGRATION_V003",
    "MIGRATION_V004",
    "MIGRATION_V005",
    "MIGRATION_V006",
]
