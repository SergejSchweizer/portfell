"""Durable, exact-selection initial-fill records backed by PostgreSQL jobs."""

from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from typing import Protocol, cast

from portfell.durable_job_repository import DurableJob, OutboxEvent, PostgresDurableJobRepository
from portfell.hosted_catalog import set_authenticated_user_sql
from portfell.project_selection_bootstrap import BootstrapError, ProjectBootstrap


class BootstrapCursor(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...

    def fetchall(self) -> list[tuple[object, ...]]: ...


class BootstrapConnection(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> BootstrapCursor: ...

    def transaction(self) -> AbstractContextManager[object]: ...


@dataclass(frozen=True)
class DurableProjectBootstrap:
    """One project-owned initial fill and its deduplicable logical worker job."""

    bootstrap: ProjectBootstrap
    job_id: str


@dataclass(frozen=True)
class InitialFillStatus:
    """Project-scoped lifecycle projection without shared-market inventory."""

    bootstrap: DurableProjectBootstrap
    status: str
    completed_units: int
    total_units: int
    terminal_code: str | None
    started_at_epoch: int | None = None
    last_progress_at_epoch: int | None = None


class ProjectBootstrapRepository(Protocol):
    """Port for creating the one immutable initial fill attached to a project."""

    def start(
        self,
        *,
        user_id: str,
        project_id: str,
        selection_id: str,
        member_ids: tuple[str, ...],
    ) -> DurableProjectBootstrap: ...

    def status(self, *, user_id: str, project_id: str) -> InitialFillStatus | None: ...


class PostgresProjectBootstrapRepository:
    """Freeze one exact selection and enqueue at most one initial-fill job per project."""

    def __init__(self, connection: BootstrapConnection) -> None:
        self._connection = connection
        self._jobs = PostgresDurableJobRepository(connection)  # type: ignore[arg-type]

    def start(
        self,
        *,
        user_id: str,
        project_id: str,
        selection_id: str,
        member_ids: tuple[str, ...],
    ) -> DurableProjectBootstrap:
        members = tuple(sorted(set(member_ids)))
        if not user_id or not project_id or not selection_id:
            raise BootstrapError("bootstrap_identity_required")
        if not members:
            raise BootstrapError("bootstrap_members_required")
        membership_hash = hashlib.sha256("\n".join(members).encode()).hexdigest()
        bootstrap = ProjectBootstrap(
            bootstrap_id=_bootstrap_id(project_id, selection_id, members),
            user_id=user_id,
            project_id=project_id,
            selection_id=selection_id,
            member_ids=members,
            selected_listing_count=len(members),
        )
        job_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"portfell:initial-fill:{bootstrap.bootstrap_id}")
        )
        with self._connection.transaction():
            self._bind(user_id)
            existing = self._existing(project_id)
            if existing is not None:
                if existing.bootstrap.status == "failed":
                    self._retry_failed_job(existing)
                    return DurableProjectBootstrap(
                        replace(existing.bootstrap, status="not_started"), existing.job_id
                    )
                return existing
            self._jobs.enqueue(
                job=DurableJob(
                    job_id=job_id,
                    user_id=user_id,
                    project_id=project_id,
                    job_kind="project_initial_fill",
                    input_hash=bootstrap.bootstrap_id,
                    input_ref=selection_id,
                ),
                event=OutboxEvent(
                    event_id=str(
                        uuid.uuid5(uuid.NAMESPACE_URL, f"portfell:initial-fill-event:{job_id}")
                    ),
                    user_id=user_id,
                    event_type="project_initial_fill.queued",
                    aggregate_ref=job_id,
                ),
            )
            self._connection.execute(
                """
insert into portfell_app.project_initial_fills (
    project_id, user_id, selection_version_id, membership_hash, selected_listing_count,
    bootstrap_job_id, status
) values (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s::uuid, 'not_started')
on conflict (project_id) do nothing
""",
                (project_id, user_id, selection_id, membership_hash, len(members), job_id),
            )
            return self._existing(project_id) or DurableProjectBootstrap(bootstrap, job_id)

    def status(self, *, user_id: str, project_id: str) -> InitialFillStatus | None:
        """Read one owned job projection; the global queue is never enumerated."""

        self._bind(user_id)
        bootstrap = self._existing(project_id)
        if bootstrap is None or bootstrap.bootstrap.user_id != user_id:
            return None
        row = self._connection.execute(
            """
select job.status, job.completed_units, job.total_units, job.terminal_code,
       extract(epoch from (
                     select attempt.started_at
           from portfell_app.job_attempts as attempt
           where attempt.job_id = job.job_id
                         and attempt.finished_at is null
                     order by attempt.attempt_number desc
                     limit 1
             ))::bigint,
             extract(epoch from job.updated_at)::bigint
from portfell_app.jobs as job
where job.job_id = %s::uuid
""",
            (bootstrap.job_id,),
        ).fetchone()
        if row is None or len(row) != 6 or not isinstance(row[0], str):
            raise BootstrapError("bootstrap_job_projection_invalid")
        if not isinstance(row[1], int) or not isinstance(row[2], int):
            raise BootstrapError("bootstrap_job_projection_invalid")
        if row[3] is not None and not isinstance(row[3], str):
            raise BootstrapError("bootstrap_job_projection_invalid")
        if row[4] is not None and not isinstance(row[4], int):
            raise BootstrapError("bootstrap_job_projection_invalid")
        if row[5] is not None and not isinstance(row[5], int):
            raise BootstrapError("bootstrap_job_projection_invalid")
        return InitialFillStatus(
            bootstrap,
            _bootstrap_status(row[0]),
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
        )

    def _existing(self, project_id: str) -> DurableProjectBootstrap | None:
        rows = self._connection.execute(
            """
select fill.user_id::text, fill.project_id::text, fill.selection_version_id::text,
       fill.membership_hash, fill.selected_listing_count, fill.status, fill.bootstrap_job_id::text,
       member.isin, member.exchange, member.code
from portfell_app.project_initial_fills as fill
join portfell_app.project_selection_members as member
  on member.selection_version_id = fill.selection_version_id
where fill.project_id = %s::uuid
order by member.isin, member.exchange, member.code
""",
            (project_id,),
        ).fetchall()
        if not rows:
            return None
        if any(
            len(row) != 10 or not all(isinstance(value, str) for value in (*row[:4], *row[5:10]))
            for row in rows
        ):
            raise BootstrapError("bootstrap_projection_invalid")
        first = rows[0]
        if not isinstance(first[4], int):
            raise BootstrapError("bootstrap_projection_invalid")
        # The catalog relationship guarantees member immutability; callers need its identity only.
        user_id, stored_project, selection_id, membership_hash, count, status, job_id, _, _, _ = (
            cast(tuple[str, str, str, str, int, str, str, str, str, str], first)
        )
        member_ids = tuple(f"{str(row[7])}:{str(row[8])}:{str(row[9])}" for row in rows)
        bootstrap = ProjectBootstrap(
            bootstrap_id=_bootstrap_id(stored_project, selection_id, member_ids),
            user_id=user_id,
            project_id=stored_project,
            selection_id=selection_id,
            member_ids=member_ids,
            selected_listing_count=count,
            status=status,
        )
        if hashlib.sha256("\n".join(member_ids).encode()).hexdigest() != membership_hash:
            raise BootstrapError("bootstrap_membership_hash_invalid")
        return DurableProjectBootstrap(bootstrap, job_id)

    def _retry_failed_job(self, existing: DurableProjectBootstrap) -> None:
        self._connection.execute(
            """
update portfell_app.jobs
set status = 'queued', completed_units = 0, total_units = 0, attempt_count = 0,
    available_at = now(), lease_owner = null, lease_token = null, lease_expires_at = null,
    heartbeat_at = null, terminal_code = null, updated_at = now()
where job_id = %s::uuid and status in ('failed', 'cancelled')
""",
            (existing.job_id,),
        )
        self._connection.execute(
            """
update portfell_app.project_initial_fills
set status = 'not_started', updated_at = now()
where bootstrap_job_id = %s::uuid
""",
            (existing.job_id,),
        )

    def _bind(self, user_id: str) -> None:
        self._connection.execute(*set_authenticated_user_sql(user_id))


def _bootstrap_id(project_id: str, selection_id: str, member_ids: tuple[str, ...]) -> str:
    payload = json.dumps(
        {"project_id": project_id, "selection_id": selection_id, "member_ids": member_ids},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _bootstrap_status(job_status: str) -> str:
    statuses = {
        "queued": "planning",
        "running": "running",
        "succeeded": "ready",
        "partial": "partial",
        "failed": "failed",
        "cancelled": "failed",
    }
    try:
        return statuses[job_status]
    except KeyError as error:
        raise BootstrapError("bootstrap_job_status_invalid") from error
