"""Restart-safe progress and lease columns for workflow commands."""

from portfell.app_state.migrations.v001_initial import AppStateMigration

_WORKFLOW_LEASES_SQL = """
alter table workflow.stage_commands
    add column if not exists progress_current bigint not null default 0
        check (progress_current >= 0),
    add column if not exists progress_total bigint
        check (progress_total is null or progress_total >= 0),
    add column if not exists progress_phase text not null default 'queued'
        check (btrim(progress_phase) <> ''),
    add column if not exists lease_expires_at timestamptz,
    add column if not exists failure_code text;

create index if not exists workflow_stage_commands_claim_idx
    on workflow.stage_commands (status, lease_expires_at, requested_at);
""".strip()

_WORKFLOW_LEASES_DOWN_SQL = """
drop index if exists workflow.workflow_stage_commands_claim_idx;
alter table workflow.stage_commands
    drop column if exists failure_code,
    drop column if exists lease_expires_at,
    drop column if exists progress_phase,
    drop column if exists progress_total,
    drop column if exists progress_current;
""".strip()

MIGRATION_V005 = AppStateMigration(
    version=5,
    name="workflow_command_leases_v5",
    sql=_WORKFLOW_LEASES_SQL,
    destructive_down_sql=_WORKFLOW_LEASES_DOWN_SQL,
)
