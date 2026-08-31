"""Forward-only migration declarations for the clean app-state database."""

from portfell.app_state.migrations.v001_initial import MIGRATION_V001
from portfell.app_state.migrations.v002_analysis_jobs import MIGRATION_V002

__all__ = ["MIGRATION_V001", "MIGRATION_V002"]
