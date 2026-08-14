"""Bounded PostgreSQL reads for tenant navigation projections."""

from __future__ import annotations

import hashlib
import json
from typing import Protocol, cast

from portfell.hosted_catalog import set_authenticated_user_sql
from portfell.table_io import JsonRow


class NavigationCursor(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...


class NavigationConnection(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> NavigationCursor: ...


class PostgresNavigationReadModel:
    """Read one already-authorized compact navigation projection."""

    def __init__(self, connection: NavigationConnection) -> None:
        self._connection = connection

    def read(self, user_id: str) -> tuple[JsonRow, str] | None:
        self._connection.execute(*set_authenticated_user_sql(user_id))
        row = self._connection.execute(
            "select payload, projection_revision from portfell_app.navigation_projections "
            "where user_id = %s::uuid",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        if len(row) != 2 or not isinstance(row[0], dict) or not isinstance(row[1], int):
            raise ValueError("navigation_projection_invalid")
        payload = cast(JsonRow, row[0])
        encoded = json.dumps(
            {"payload": payload, "revision": row[1]}, sort_keys=True, separators=(",", ":")
        ).encode()
        return payload, hashlib.sha256(encoded).hexdigest()

    def write(self, user_id: str, payload: JsonRow) -> tuple[JsonRow, str]:
        """Upsert one canonical projection in the caller's existing transaction."""

        self._connection.execute(*set_authenticated_user_sql(user_id))
        row = self._connection.execute(
            """
insert into portfell_app.navigation_projections (user_id, payload, projection_revision)
values (%s::uuid, %s::jsonb, 1)
on conflict (user_id) do update
set payload = excluded.payload,
    projection_revision = case
        when portfell_app.navigation_projections.payload is distinct from excluded.payload
        then portfell_app.navigation_projections.projection_revision + 1
        else portfell_app.navigation_projections.projection_revision
    end,
    updated_at = case
        when portfell_app.navigation_projections.payload is distinct from excluded.payload
        then now()
        else portfell_app.navigation_projections.updated_at
    end
returning payload, projection_revision
""",
            (user_id, json.dumps(payload, sort_keys=True, separators=(",", ":"))),
        ).fetchone()
        if (
            row is None
            or len(row) != 2
            or not isinstance(row[0], dict)
            or not isinstance(row[1], int)
        ):
            raise ValueError("navigation_projection_write_invalid")
        written = cast(JsonRow, row[0])
        encoded = json.dumps(
            {"payload": written, "revision": row[1]}, sort_keys=True, separators=(",", ":")
        ).encode()
        return written, hashlib.sha256(encoded).hexdigest()
