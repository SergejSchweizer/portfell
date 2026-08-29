from __future__ import annotations

import pytest

from portfell.hosted_idempotency_repository import (
    IdempotencyConflictError,
    PostgresIdempotencyRepository,
)


class _Cursor:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class _Connection:
    def __init__(self, row: tuple[object, ...] | None = None) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self._row = row

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        return _Cursor(self._row if "select request_hash" in sql else None)


def test_postgres_idempotency_lookup_binds_user_and_returns_matching_response() -> None:
    connection = _Connection(("request-hash", "response-id"))

    value = PostgresIdempotencyRepository(connection).lookup(
        user_id="user-1", operation="project:income", key="request-1", request_hash="request-hash"
    )

    assert value == "response-id"
    assert connection.calls[0] == (
        "select set_config(%s, %s, true)",
        ("portfell.current_user_id", "user-1"),
    )
    assert connection.calls[1][1] == ("project:income", "request-1")


def test_postgres_idempotency_rejects_a_key_reused_for_other_command() -> None:
    connection = _Connection(("original-hash", "response-id"))

    with pytest.raises(IdempotencyConflictError, match="idempotency_payload_conflict"):
        PostgresIdempotencyRepository(connection).lookup(
            user_id="user-1",
            operation="project:income",
            key="request-1",
            request_hash="changed-hash",
        )


def test_postgres_idempotency_remember_skips_missing_key_and_uses_owned_insert() -> None:
    connection = _Connection()
    repository = PostgresIdempotencyRepository(connection)

    repository.remember(
        user_id="user-1",
        operation="project:income",
        key=None,
        request_hash="request-hash",
        response_ref="project-id",
    )
    assert connection.calls == []

    repository.remember(
        user_id="user-1",
        operation="project:income",
        key="request-1",
        request_hash="request-hash",
        response_ref="project-id",
    )
    assert connection.calls[0][1] == ("portfell.current_user_id", "user-1")
    statement, parameters = connection.calls[1]
    assert "on conflict (user_id, operation, idempotency_key) do nothing" in statement
    assert parameters == ("user-1", "project:income", "request-1", "request-hash", "project-id")
