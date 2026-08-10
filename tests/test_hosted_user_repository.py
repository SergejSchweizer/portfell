from __future__ import annotations

import pytest

from portfell.hosted_user_repository import (
    HostedUser,
    HostedUserError,
    PostgresHostedUserRepository,
)


class _Cursor:
    def __init__(self, row: tuple[object, ...] | None = None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        if "select user_id::text" in sql:
            return _Cursor((parameters[0], "active"))
        return _Cursor()


def test_postgres_user_repository_binds_user_for_idempotent_create_and_read() -> None:
    connection = _Connection()
    repository = PostgresHostedUserRepository(connection)
    user_id = "00000000-0000-0000-0000-000000000001"

    assert repository.create(user_id) == HostedUser(user_id, "active")

    statements = "\n".join(statement for statement, _ in connection.calls)
    assert connection.calls[0] == (
        "select set_config(%s, %s, true)",
        ("portfell.current_user_id", user_id),
    )
    assert "on conflict (user_id) do nothing" in statements
    assert "select user_id::text, status" in statements


def test_postgres_user_repository_soft_deletes_with_parameterized_owned_command() -> None:
    connection = _Connection()
    user_id = "00000000-0000-0000-0000-000000000001"

    PostgresHostedUserRepository(connection).soft_delete(user_id)

    assert connection.calls[0][1] == ("portfell.current_user_id", user_id)
    statement, parameters = connection.calls[1]
    assert "set status = 'deleted'" in statement
    assert parameters == (user_id,)


def test_postgres_user_repository_rejects_missing_or_invalid_user_projections() -> None:
    class _MissingConnection(_Connection):
        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
            self.calls.append((sql, parameters))
            return _Cursor()

    user_id = "00000000-0000-0000-0000-000000000001"
    with pytest.raises(HostedUserError, match="hosted_user_not_found"):
        PostgresHostedUserRepository(_MissingConnection()).create(user_id)

    class _InvalidConnection(_Connection):
        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
            self.calls.append((sql, parameters))
            return _Cursor((user_id, "unexpected"))

    with pytest.raises(HostedUserError, match="hosted_user_projection_invalid"):
        PostgresHostedUserRepository(_InvalidConnection()).get(user_id)

    class _MalformedConnection(_Connection):
        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
            self.calls.append((sql, parameters))
            return _Cursor((user_id,))

    with pytest.raises(HostedUserError, match="hosted_user_projection_invalid"):
        PostgresHostedUserRepository(_MalformedConnection()).get(user_id)
