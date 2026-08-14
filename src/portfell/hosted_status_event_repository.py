"""Bounded durable status-event append and replay adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from portfell.hosted_catalog import set_authenticated_user_sql


class StatusEventCursor(Protocol):
    def fetchall(self) -> list[tuple[object, ...]]: ...


class StatusEventConnection(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> StatusEventCursor: ...


@dataclass(frozen=True)
class HostedStatusEvent:
    event_id: int
    event_type: str
    aggregate_ref: str
    projection_revision: str | None
    terminal_status: str | None


class PostgresStatusEventRepository:
    """Store compact events and replay at most the configured bounded page."""

    def __init__(self, connection: StatusEventConnection) -> None:
        self._connection = connection

    def append(
        self,
        *,
        user_id: str,
        project_id: str | None,
        event_type: str,
        aggregate_ref: str,
        projection_revision: str | None = None,
        terminal_status: str | None = None,
    ) -> None:
        self._bind(user_id)
        self._connection.execute(
            """
insert into portfell_app.status_events (
    user_id, project_id, event_type, aggregate_ref, projection_revision, terminal_status
) values (%s::uuid, %s::uuid, %s, %s, %s, %s)
""",
            (user_id, project_id, event_type, aggregate_ref, projection_revision, terminal_status),
        )

    def replay(
        self,
        *,
        user_id: str,
        after_event_id: int,
        limit: int = 1_000,
    ) -> tuple[HostedStatusEvent, ...]:
        if after_event_id < 0 or limit < 1 or limit > 1_000:
            raise ValueError("status_event_replay_invalid")
        self._bind(user_id)
        rows = self._connection.execute(
            """
select event_id, event_type, aggregate_ref, projection_revision, terminal_status
from portfell_app.status_events
where user_id = %s::uuid and event_id > %s
order by event_id
limit %s
""",
            (user_id, after_event_id, limit),
        ).fetchall()
        return tuple(_event(row) for row in rows)

    def _bind(self, user_id: str) -> None:
        if getattr(self._connection, "authenticated_user_id", None) != user_id:
            self._connection.execute(*set_authenticated_user_sql(user_id))


def _event(row: tuple[object, ...]) -> HostedStatusEvent:
    if (
        len(row) != 5
        or not isinstance(row[0], int)
        or not isinstance(row[1], str)
        or not isinstance(row[2], str)
        or row[3] is not None and not isinstance(row[3], str)
        or row[4] is not None and not isinstance(row[4], str)
    ):
        raise ValueError("status_event_row_invalid")
    return HostedStatusEvent(row[0], row[1], row[2], row[3], row[4])
