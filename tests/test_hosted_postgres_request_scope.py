from __future__ import annotations

import pytest

from portfell.hosted_postgres_request_scope import (
    RequestScopedPostgresConnection,
    ScopedConnectionError,
)


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> None:
        self.calls.append((sql, parameters))

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def test_request_scoped_connection_requires_authenticated_scope() -> None:
    connection = RequestScopedPostgresConnection(_Connection)

    with pytest.raises(ScopedConnectionError, match="postgres_request_scope_required"):
        connection.execute("select 1")


def test_request_scoped_connection_binds_rls_and_commits() -> None:
    created: list[_Connection] = []
    scope = RequestScopedPostgresConnection(lambda: created.append(_Connection()) or created[-1])

    with scope.request("00000000-0000-5000-8000-000000000001"):
        scope.execute("select project_id from portfell_app.projects")

    connection = created[0]
    assert connection.calls[0] == (
        "select set_config(%s, %s, true)",
        ("portfell.current_user_id", "00000000-0000-5000-8000-000000000001"),
    )
    assert connection.calls[1] == ("select project_id from portfell_app.projects", ())
    assert connection.committed
    assert not connection.rolled_back
    assert connection.closed


def test_request_scoped_connection_rolls_back_on_exception() -> None:
    created: list[_Connection] = []
    scope = RequestScopedPostgresConnection(lambda: created.append(_Connection()) or created[-1])

    with (
        pytest.raises(RuntimeError, match="boom"),
        scope.request("00000000-0000-5000-8000-000000000001"),
    ):
        raise RuntimeError("boom")

    assert created[0].rolled_back
    assert not created[0].committed
    assert created[0].closed


def test_transaction_reuses_the_authenticated_request_connection() -> None:
    created: list[_Connection] = []
    scope = RequestScopedPostgresConnection(lambda: created.append(_Connection()) or created[-1])

    with scope.request("00000000-0000-5000-8000-000000000001"), scope.transaction():
        scope.execute("select 1")

    assert len(created) == 1
    assert created[0].calls[-1] == ("select 1", ())


def test_worker_transaction_owns_and_commits_a_connection() -> None:
    created: list[_Connection] = []
    scope = RequestScopedPostgresConnection(lambda: created.append(_Connection()) or created[-1])

    with scope.transaction():
        scope.execute("select 1")

    assert created[0].committed
    assert created[0].closed
