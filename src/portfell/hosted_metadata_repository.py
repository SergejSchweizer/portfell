"""Durable PostgreSQL control plane for hosted metadata lifecycle commands."""

# ruff: noqa: E501

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID

from portfell.hosted_catalog import set_authenticated_user_sql
from portfell.table_io import JsonRow


class MetadataRepositoryError(ValueError):
    """Raised when a durable metadata control-plane command is invalid."""


@dataclass(frozen=True)
class MetadataRun:
    """Payload-free durable metadata lifecycle record."""

    metadata_run_id: str
    user_id: str
    status: str
    total: int
    completed: int
    skipped_exchange_count: int
    percent: int
    summary: JsonRow


class MetadataCursor(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...


class MetadataConnection(Protocol):
    def transaction(self) -> AbstractContextManager[object]: ...

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> MetadataCursor: ...


class MetadataLifecycleRepository(Protocol):
    def create(self, run: MetadataRun) -> MetadataRun: ...

    def status(self, *, user_id: str, run_id: str) -> MetadataRun | None: ...

    def update(self, run: MetadataRun) -> MetadataRun: ...

    def set_revision(self, *, user_id: str, revision_id: str) -> None: ...

    def revision(self, *, user_id: str) -> str | None: ...

    def idempotent_response(
        self, *, user_id: str, operation: str, key: str, request_hash: str
    ) -> str | None: ...

    def remember_idempotency(
        self, *, user_id: str, operation: str, key: str, request_hash: str, response_ref: str
    ) -> None: ...


class PostgresMetadataLifecycleRepository:
    """RLS-bound metadata status and request-idempotency adapter."""

    def __init__(
        self,
        connection: MetadataConnection,
        *,
        navigation_refresher: Callable[[str], object] | None = None,
    ) -> None:
        self._connection = connection
        self._navigation_refresher = navigation_refresher

    def create(self, run: MetadataRun) -> MetadataRun:
        with self._connection.transaction():
            self._bind(run.user_id)
            self._connection.execute(
                "insert into portfell_app.metadata_runs (metadata_run_id, user_id, status, total, completed, skipped_exchange_count, percent, summary) values (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::jsonb) on conflict (metadata_run_id) do nothing",
                _parameters(run),
            )
            self._refresh_navigation(run.user_id)
        return run

    def status(self, *, user_id: str, run_id: str) -> MetadataRun | None:
        try:
            UUID(run_id)
        except ValueError:
            return None
        with self._connection.transaction():
            self._bind(user_id)
            row = self._connection.execute(
                "select metadata_run_id::text, user_id::text, status, total, completed, skipped_exchange_count, percent, summary from portfell_app.metadata_runs where metadata_run_id = %s::uuid",
                (run_id,),
            ).fetchone()
        return _run(row)

    def update(self, run: MetadataRun) -> MetadataRun:
        with self._connection.transaction():
            self._bind(run.user_id)
            self._connection.execute(
                "update portfell_app.metadata_runs set status = %s, total = %s, completed = %s, skipped_exchange_count = %s, percent = %s, summary = %s::jsonb, updated_at = now() where metadata_run_id = %s::uuid",
                (*_parameters(run)[2:], run.metadata_run_id),
            )
            self._refresh_navigation(run.user_id)
        return run

    def set_revision(self, *, user_id: str, revision_id: str) -> None:
        with self._connection.transaction():
            self._bind(user_id)
            self._connection.execute(
                "insert into portfell_app.metadata_revision_pointers (user_id, revision_id) values (%s::uuid, %s) on conflict (user_id) do update set revision_id = excluded.revision_id, updated_at = now()",
                (user_id, revision_id),
            )
            self._refresh_navigation(user_id)

    def revision(self, *, user_id: str) -> str | None:
        with self._connection.transaction():
            self._bind(user_id)
            row = self._connection.execute(
                "select revision_id from portfell_app.metadata_revision_pointers where user_id = %s::uuid",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        if len(row) != 1 or not isinstance(row[0], str):
            raise MetadataRepositoryError("metadata_revision_projection_invalid")
        return row[0]

    def idempotent_response(
        self, *, user_id: str, operation: str, key: str, request_hash: str
    ) -> str | None:
        with self._connection.transaction():
            self._bind(user_id)
            row = self._connection.execute(
                "select response_ref, request_hash from portfell_app.request_idempotency where user_id = %s::uuid and operation = %s and idempotency_key = %s",
                (user_id, operation, key),
            ).fetchone()
        if row is None:
            return None
        if len(row) != 2 or not isinstance(row[0], str) or not isinstance(row[1], str):
            raise MetadataRepositoryError("idempotency_projection_invalid")
        if row[1] != request_hash:
            raise MetadataRepositoryError("idempotency_payload_conflict")
        return row[0]

    def remember_idempotency(
        self, *, user_id: str, operation: str, key: str, request_hash: str, response_ref: str
    ) -> None:
        with self._connection.transaction():
            self._bind(user_id)
            self._connection.execute(
                "insert into portfell_app.request_idempotency (user_id, operation, idempotency_key, request_hash, response_ref) values (%s::uuid, %s, %s, %s, %s) on conflict (user_id, operation, idempotency_key) do nothing",
                (user_id, operation, key, request_hash, response_ref),
            )

    def _refresh_navigation(self, user_id: str) -> None:
        if self._navigation_refresher is not None:
            self._navigation_refresher(user_id)

    def _bind(self, user_id: str) -> None:
        self._connection.execute(*set_authenticated_user_sql(user_id))


def _parameters(run: MetadataRun) -> tuple[object, ...]:
    return (
        run.metadata_run_id,
        run.user_id,
        run.status,
        run.total,
        run.completed,
        run.skipped_exchange_count,
        run.percent,
        json.dumps(run.summary, sort_keys=True, separators=(",", ":")),
    )


def _run(row: tuple[object, ...] | None) -> MetadataRun | None:
    if row is None:
        return None
    if (
        len(row) != 8
        or not isinstance(row[0], str)
        or not isinstance(row[1], str)
        or not isinstance(row[2], str)
        or not all(isinstance(value, int) and value >= 0 for value in row[3:7])
        or not isinstance(row[7], dict)
    ):
        raise MetadataRepositoryError("metadata_run_projection_invalid")
    return MetadataRun(
        row[0],
        row[1],
        row[2],
        cast(int, row[3]),
        cast(int, row[4]),
        cast(int, row[5]),
        cast(int, row[6]),
        dict(cast(dict[str, object], row[7])),
    )
