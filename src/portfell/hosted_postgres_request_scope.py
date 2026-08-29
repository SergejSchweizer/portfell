"""Request-scoped PostgreSQL connections for RLS-bound hosted services."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from threading import Thread
from typing import Any, Protocol

from portfell.hosted_catalog import set_authenticated_user_sql


class ScopedConnectionError(RuntimeError):
    """Raised when a repository is used outside an authenticated request scope."""


class ScopedConnection(Protocol):
    autocommit: bool

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
        self._after_commit: ContextVar[list[Callable[[], None]] | None] = ContextVar(
            "portfell_postgres_after_commit", default=None
        )
        self._authenticated_user: ContextVar[str | None] = ContextVar(
            "portfell_postgres_authenticated_user", default=None
        )
        self._statement_count: ContextVar[int | None] = ContextVar(
            "portfell_postgres_statement_count", default=None
        )

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> Any:
        connection = self._current.get()
        if connection is None:
            raise ScopedConnectionError("postgres_request_scope_required")
        count = self._statement_count.get()
        if count is not None:
            self._statement_count.set(count + 1)
        return connection.execute(sql, parameters)

    @property
    def authenticated_user_id(self) -> str | None:
        """Return the current RLS principal without issuing a PostgreSQL statement."""

        return self._authenticated_user.get()

    @property
    def statement_count(self) -> int | None:
        """Return statements executed in the current request/worker scope."""

        return self._statement_count.get()

    @contextmanager
    def transaction(self) -> Generator[None]:
        """Reuse an authenticated request transaction or own one worker transaction."""

        if self._current.get() is not None:
            yield
            return
        connection = self._connect()
        token: Token[ScopedConnection | None] = self._current.set(connection)
        statement_token = self._statement_count.set(0)
        try:
            yield
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            self._current.reset(token)
            self._statement_count.reset(statement_token)
            connection.close()

    @contextmanager
    def request(self, user_id: str) -> Generator[None]:
        """Bind one user to one transaction and commit only successful requests."""

        connection = self._connect()
        token: Token[ScopedConnection | None] = self._current.set(connection)
        user_token = self._authenticated_user.set(user_id)
        statement_token = self._statement_count.set(0)
        callbacks: list[Callable[[], None]] = []
        after_commit_token = self._after_commit.set(callbacks)
        committed = False
        try:
            self.execute(*set_authenticated_user_sql(user_id))
            yield
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()
            committed = True
        finally:
            self._current.reset(token)
            self._authenticated_user.reset(user_token)
            self._statement_count.reset(statement_token)
            self._after_commit.reset(after_commit_token)
            connection.close()
        if committed:
            for callback in callbacks:
                callback()

    def spawn_after_commit(self, *, user_id: str, operation: Callable[[], None]) -> None:
        """Start an operation with visible incremental RLS updates after the request commits."""

        callbacks = self._after_commit.get()
        if callbacks is None:
            raise ScopedConnectionError("postgres_request_scope_required")

        def run() -> None:
            with self.background_request(user_id):
                operation()

        callbacks.append(lambda: Thread(target=run, name="portfell-research", daemon=True).start())

    @contextmanager
    def background_request(self, user_id: str) -> Generator[None]:
        """Bind one user to an autocommit connection for long-running background work."""

        connection = self._connect()
        connection.autocommit = True
        token: Token[ScopedConnection | None] = self._current.set(connection)
        user_token = self._authenticated_user.set(user_id)
        statement_token = self._statement_count.set(0)
        try:
            self.execute(
                "select set_config(%s, %s, false)",
                ("portfell.current_user_id", user_id),
            )
            yield
        finally:
            self._current.reset(token)
            self._authenticated_user.reset(user_token)
            self._statement_count.reset(statement_token)
            connection.close()
