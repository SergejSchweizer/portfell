"""Retention policy for compact hosted status events."""

HOSTED_STATUS_EVENT_RETENTION_SCHEMA_SQL = """
drop policy if exists status_event_retention on portfell_app.status_events;
create policy status_event_retention on portfell_app.status_events
    for delete to portfell_app
    using (occurred_at < now() - interval '24 hours');
"""
