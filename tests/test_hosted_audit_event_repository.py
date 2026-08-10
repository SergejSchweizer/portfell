from __future__ import annotations

from portfell.hosted_audit_event_repository import (
    HostedAuditEvent,
    PostgresAuditEventRepository,
)


class _Cursor:
    pass


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        return _Cursor()


def test_postgres_audit_repository_binds_user_and_appends_immutable_event() -> None:
    connection = _Connection()
    event = HostedAuditEvent(
        audit_event_id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000002",
        event_type="project_created",
        subject_ref="project-1",
        metadata={"project_id": "project-1"},
    )

    assert PostgresAuditEventRepository(connection).append(event) == event

    assert connection.calls[0] == (
        "select set_config(%s, %s, true)",
        ("portfell.current_user_id", event.user_id),
    )
    statement, parameters = connection.calls[1]
    assert "insert into portfell_app.audit_events" in statement
    assert "update " not in statement.lower()
    assert parameters[-1] == '{"project_id":"project-1"}'