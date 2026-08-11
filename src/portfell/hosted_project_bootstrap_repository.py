"""Durable, exact-selection initial-fill records backed by PostgreSQL jobs."""

from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

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
            first
        )
        member_ids = tuple(f"{row[7]}:{row[8]}:{row[9]}" for row in rows)
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

    def _bind(self, user_id: str) -> None:
        self._connection.execute(*set_authenticated_user_sql(user_id))


def _bootstrap_id(project_id: str, selection_id: str, member_ids: tuple[str, ...]) -> str:
    payload = json.dumps(
        {"project_id": project_id, "selection_id": selection_id, "member_ids": member_ids},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()
