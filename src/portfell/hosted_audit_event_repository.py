"""PostgreSQL repository for append-only hosted audit events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from portfell.hosted_catalog import set_authenticated_user_sql


@dataclass(frozen=True)
class HostedAuditEvent:
    """One user-scoped, immutable audit record with allow-listed metadata."""

    audit_event_id: str
    user_id: str
    event_type: str
    subject_ref: str
    metadata: dict[str, object]


class AuditEventCursor(Protocol):
    """Minimal result boundary for append-only audit commands."""


class AuditEventConnection(Protocol):
    """Parameterized connection boundary for audit event commands."""

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> AuditEventCursor: ...


class PostgresAuditEventRepository:
    """Append immutable user-scoped audit events after transaction-local RLS binding."""

    def __init__(self, connection: AuditEventConnection) -> None:
        self._connection = connection

    def append(self, event: HostedAuditEvent) -> HostedAuditEvent:
        """Persist one immutable event without exposing values through SQL text."""

        self._connection.execute(*set_authenticated_user_sql(event.user_id))
        self._connection.execute(
            """
insert into portfell_app.audit_events (
    audit_event_id, user_id, event_type, subject_ref, metadata
) values (%s::uuid, %s::uuid, %s, %s, %s::jsonb)
""",
            (
                event.audit_event_id,
                event.user_id,
                event.event_type,
                event.subject_ref,
                json.dumps(event.metadata, sort_keys=True, separators=(",", ":")),
            ),
        )
        return event
