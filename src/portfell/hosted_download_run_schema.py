"""PostgreSQL schema fragments for hosted provider download runs."""

DOWNLOAD_RUN_PARTIAL_STATUS_SQL = """
alter table portfell_app.download_runs
    drop constraint if exists download_runs_status_check;
alter table portfell_app.download_runs
    add constraint download_runs_status_check
    check (status in ('planned', 'running', 'succeeded', 'failed', 'partial'));
"""
