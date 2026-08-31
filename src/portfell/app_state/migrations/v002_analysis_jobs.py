"""Durable staged-analysis job and progress migration."""

from portfell.app_state.migrations.v001_initial import AppStateMigration
from portfell.app_state.schema import V2_ANALYSIS_JOBS_DOWN_SQL, V2_ANALYSIS_JOBS_SQL

MIGRATION_V002 = AppStateMigration(
    version=2,
    name="durable_analysis_jobs_v2",
    sql=V2_ANALYSIS_JOBS_SQL,
    destructive_down_sql=V2_ANALYSIS_JOBS_DOWN_SQL,
)
