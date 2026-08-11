"""Durable idempotency records for user-scoped hosted commands."""

from __future__ import annotations

from typing import Protocol

from portfell.hosted_api_state import HostedApiState
from portfell.hosted_catalog import set_authenticated_user_sql


class IdempotencyConflictError(ValueError):
    """Raised when one idempotency key is reused with a different command."""


class IdempotencyCursor(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...


class IdempotencyConnection(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> IdempotencyCursor: ...


class IdempotencyRepository(Protocol):
    def lookup(
        self, *, user_id: str, operation: str, key: str | None, request_hash: str
    ) -> str | None: ...

    def remember(
        self,
        *,
        user_id: str,
        operation: str,
        key: str | None,
        request_hash: str,
        response_ref: str,
    ) -> None: ...


class LocalIdempotencyRepository:
    """Explicit temporary adapter for the pre-cutover development state."""

    def __init__(self, state: HostedApiState) -> None:
        self._state = state

    def lookup(
        self, *, user_id: str, operation: str, key: str | None, request_hash: str
    ) -> str | None:
        del request_hash
        return None if key is None else self._state.idempotency_refs.get((user_id, operation, key))

    def remember(
        self,
        *,
        user_id: str,
        operation: str,
        key: str | None,
        request_hash: str,
        response_ref: str,
    ) -> None:
        del request_hash
        if key is not None:
            self._state.idempotency_refs[(user_id, operation, key)] = response_ref


class PostgresIdempotencyRepository:
    """RLS-bound request de-duplication backed by ``request_idempotency``."""

    def __init__(self, connection: IdempotencyConnection) -> None:
        self._connection = connection

    def lookup(
        self, *, user_id: str, operation: str, key: str | None, request_hash: str
    ) -> str | None:
        if key is None:
            return None
        self._bind(user_id)
        row = self._connection.execute(
            """
select request_hash, response_ref
from portfell_app.request_idempotency
where operation = %s and idempotency_key = %s
""",
            (operation, key),
        ).fetchone()
        if row is None:
            return None
        if len(row) != 2 or not isinstance(row[0], str) or not isinstance(row[1], str):
            raise ValueError("idempotency_projection_invalid")
        if row[0] != request_hash:
            raise IdempotencyConflictError("idempotency_payload_conflict")
        return row[1]

    def remember(
        self,
        *,
        user_id: str,
        operation: str,
        key: str | None,
        request_hash: str,
        response_ref: str,
    ) -> None:
        if key is None:
            return
        self._bind(user_id)
        self._connection.execute(
            """
insert into portfell_app.request_idempotency (
    user_id, operation, idempotency_key, request_hash, response_ref
) values (%s::uuid, %s, %s, %s, %s)
on conflict (user_id, operation, idempotency_key) do nothing
""",
            (user_id, operation, key, request_hash, response_ref),
        )

    def _bind(self, user_id: str) -> None:
        self._connection.execute(*set_authenticated_user_sql(user_id))
