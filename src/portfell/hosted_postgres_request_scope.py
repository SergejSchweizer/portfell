"""Request-scoped PostgreSQL connections for RLS-bound hosted services."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any, Protocol

from portfell.hosted_catalog import set_authenticated_user_sql


class ScopedConnectionError(RuntimeError):
    """Raised when a repository is used outside an authenticated request scope."""


class ScopedConnection(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> Any: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


ConnectionFactory = Callable[[], ScopedConnection]


class RequestScopedPostgresConnection:
    """Expose the request's transaction to repositories without a global connection."""

    def __init__(self, connect: ConnectionFactory) -> None:
        self._connect = connect
        self._current: ContextVar[ScopedConnection | None] = ContextVar(
            "portfell_postgres_connection", default=None
        )

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> Any:
        connection = self._current.get()
        if connection is None:
            raise ScopedConnectionError("postgres_request_scope_required")
        return connection.execute(sql, parameters)

    @contextmanager
    def transaction(self) -> Generator[None]:
        """Reuse an authenticated request transaction or own one worker transaction."""

        if self._current.get() is not None:
            yield
            return
        connection = self._connect()
        token: Token[ScopedConnection | None] = self._current.set(connection)
        try:
            yield
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            self._current.reset(token)
            connection.close()

    @contextmanager
    def request(self, user_id: str) -> Generator[None]:
        """Bind one user to one transaction and commit only successful requests."""

        connection = self._connect()
        token: Token[ScopedConnection | None] = self._current.set(connection)
        try:
            connection.execute(*set_authenticated_user_sql(user_id))
            yield
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            self._current.reset(token)
            connection.close()
