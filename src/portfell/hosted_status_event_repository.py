"""Bounded durable status-event append and replay adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from portfell.hosted_catalog import set_authenticated_user_sql


class StatusEventCursor(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...

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

    def bounds(self, *, user_id: str) -> tuple[int | None, int | None]:
        """Return the oldest and newest retained IDs visible to one user only."""

        self._bind(user_id)
        row = self._connection.execute(
            """
select min(event_id), max(event_id)
from portfell_app.status_events
where user_id = %s::uuid
""",
            (user_id,),
        ).fetchone()
        if row is None:
            return None, None
        if len(row) != 2 or any(value is not None and not isinstance(value, int) for value in row):
            raise ValueError("status_event_bounds_invalid")
        return cast(int | None, row[0]), cast(int | None, row[1])

    def has_more(self, *, user_id: str, after_event_id: int) -> bool:
        """Check whether a bounded replay page omitted newer authorized events."""

        self._bind(user_id)
        row = self._connection.execute(
            """
select exists(
    select 1 from portfell_app.status_events
    where user_id = %s::uuid and event_id > %s
)
""",
            (user_id, after_event_id),
        ).fetchone()
        if row is None or len(row) != 1 or not isinstance(row[0], bool):
            raise ValueError("status_event_bounds_invalid")
        return row[0]

    def prune_expired(self) -> int:
        """Delete only globally expired compact events under the retention RLS policy."""

        rows = self._connection.execute(
            """
delete from portfell_app.status_events
where occurred_at < now() - interval '24 hours'
returning event_id
"""
        ).fetchall()
        if any(len(row) != 1 or not isinstance(row[0], int) for row in rows):
            raise ValueError("status_event_retention_invalid")
        return len(rows)

    def _bind(self, user_id: str) -> None:
        if getattr(self._connection, "authenticated_user_id", None) != user_id:
            self._connection.execute(*set_authenticated_user_sql(user_id))


def _event(row: tuple[object, ...]) -> HostedStatusEvent:
    if (
        len(row) != 5
        or not isinstance(row[0], int)
        or not isinstance(row[1], str)
        or not isinstance(row[2], str)
        or row[3] is not None
        and not isinstance(row[3], str)
        or row[4] is not None
        and not isinstance(row[4], str)
    ):
        raise ValueError("status_event_row_invalid")
    return HostedStatusEvent(row[0], row[1], row[2], row[3], row[4])
