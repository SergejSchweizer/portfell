"""Durable claims for worker-owned shared metadata refreshes."""

from __future__ import annotations

import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ClaimedMetadataRefresh:
    """One metadata run exclusively leased to the operations worker."""

    metadata_run_id: str
    user_id: str
    lease_token: str


class Cursor(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...


class Connection(Protocol):
    def transaction(self) -> AbstractContextManager[object]: ...

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> Cursor: ...


class PostgresMetadataRefreshJobRepository:
    """Queue metadata refreshes without granting the API shared-store writes."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def enqueue(self, *, metadata_run_id: str, user_id: str) -> None:
        with self._connection.transaction():
            self._connection.execute(
                """
insert into portfell_app.metadata_refresh_jobs (metadata_run_id, user_id, status)
values (%s::uuid, %s::uuid, 'queued')
on conflict (metadata_run_id) do nothing
""",
                (metadata_run_id, user_id),
            )

    def claim(self) -> ClaimedMetadataRefresh | None:
        lease_token = str(uuid.uuid4())
        with self._connection.transaction():
            row = self._connection.execute(
                """
with claimable as (
    select metadata_run_id
    from portfell_app.metadata_refresh_jobs
    where status = 'queued'
       or (status = 'running' and lease_expires_at <= now())
    order by created_at, metadata_run_id
    limit 1
    for update skip locked
)
update portfell_app.metadata_refresh_jobs as job
set status = 'running', lease_token = %s::uuid,
    lease_expires_at = now() + interval '5 minutes', updated_at = now()
from claimable
where job.metadata_run_id = claimable.metadata_run_id
returning job.metadata_run_id::text, job.user_id::text
""",
                (lease_token,),
            ).fetchone()
        if row is None:
            return None
        if len(row) != 2 or not isinstance(row[0], str) or not isinstance(row[1], str):
            raise ValueError("metadata_refresh_job_projection_invalid")
        return ClaimedMetadataRefresh(row[0], row[1], lease_token)

    def complete(self, claim: ClaimedMetadataRefresh, *, succeeded: bool) -> None:
        with self._connection.transaction():
            updated = self._connection.execute(
                """
update portfell_app.metadata_refresh_jobs
set status = %s, lease_token = null, lease_expires_at = null, updated_at = now()
where metadata_run_id = %s::uuid and status = 'running' and lease_token = %s::uuid
returning metadata_run_id
""",
                ("succeeded" if succeeded else "failed", claim.metadata_run_id, claim.lease_token),
            ).fetchone()
        if updated is None:
            raise ValueError("metadata_refresh_job_lease_lost")
