"""Read-only repeatable-read connection helpers for market snapshots."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Protocol

from portfell.market_source.errors import (
    MARKET_SOURCE_ROLE_INVALID,
    MARKET_SOURCE_UNAVAILABLE,
    MarketSourceError,
)


class Cursor(Protocol):
    def execute(self, query: str, parameters: object = ...) -> object: ...

    def fetchone(self) -> tuple[object, ...] | None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...

    def close(self) -> None: ...


def validate_reader_role(cursor: Cursor, *, role: str, member_of: str) -> None:
    """Require the configured login role to be a non-superuser group member."""
    cursor.execute(
        "SELECT rolcanlogin, rolsuper, pg_has_role(current_user, %s, 'member') "
        "FROM pg_roles WHERE rolname = current_user",
        (member_of,),
    )
    row = cursor.fetchone()
    if row != (True, False, True):
        raise MarketSourceError(MARKET_SOURCE_ROLE_INVALID)


@contextmanager
def repeatable_read_snapshot(
    connection: Connection, *, role: str, member_of: str
) -> Generator[Cursor]:
    """Open one UTC, read-only, repeatable-read transaction and always close it."""
    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute("SET LOCAL TIME ZONE 'UTC'")
        validate_reader_role(cursor, role=role, member_of=member_of)
        yield cursor
        cursor.execute("COMMIT")
    except MarketSourceError:
        raise
    except Exception as error:
        raise MarketSourceError(MARKET_SOURCE_UNAVAILABLE) from error
    finally:
        connection.close()
