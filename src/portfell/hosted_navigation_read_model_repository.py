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
