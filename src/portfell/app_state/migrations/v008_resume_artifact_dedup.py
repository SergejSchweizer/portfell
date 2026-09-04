"""Allow identical immutable artifact content to be published by resumed runs."""

from portfell.app_state.migrations.v001_initial import AppStateMigration


MIGRATION_V008 = AppStateMigration(
    version=8,
    name="resume_artifact_content_scope_v8",
    sql="""
    alter table portfell.analysis_artifacts
        drop constraint if exists analysis_artifacts_artifact_type_content_hash_key;
    """.strip(),
    destructive_down_sql="",
)
