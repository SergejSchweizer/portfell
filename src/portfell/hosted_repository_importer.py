"""D017 tenant repository ports and read-only local-workspace importer."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol, cast

from portfell.hosted_catalog import set_authenticated_user_sql


class TenantImportError(ValueError):
    """Raised when legacy local-workspace state cannot be safely imported."""


@dataclass(frozen=True, order=True)
class TenantProject:
    """Normalized project control-plane record for a future PostgreSQL adapter."""

    project_id: str
    user_id: str
    name: str


@dataclass(frozen=True, order=True)
class TenantSelection:
    """Normalized immutable selection membership imported from local workspace state."""

    selection_id: str
    project_id: str
    user_id: str
    name: str
    member_ids: tuple[str, ...]


@dataclass(frozen=True)
class ImportReport:
    """Deterministic, redacted summary for one local-workspace import plan."""

    checksum: str
    project_count: int
    selection_count: int
    membership_count: int
    dry_run: bool


class TenantRepository(Protocol):
    """Control-plane persistence port; implementations own transaction boundaries."""

    def import_snapshot(
        self,
        *,
        checksum: str,
        projects: tuple[TenantProject, ...],
        selections: tuple[TenantSelection, ...],
        current_projects: Mapping[str, str],
    ) -> None:
        """Persist one validated legacy snapshot atomically or reject it."""

    def imported_checksums(self) -> tuple[str, ...]:
        """Return deterministic completed-import identifiers."""

        ...


class TenantCursor(Protocol):
    """Minimal PostgreSQL result boundary for tenant repository projections."""

    def fetchall(self) -> list[tuple[object, ...]]:
        """Return all selected rows."""

        ...


class TenantConnection(Protocol):
    """Parameterized connection contract; callers provide transaction ownership."""

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> TenantCursor:
        """Execute parameterized SQL."""

        ...


class PostgresTenantProjectionRepository:
    """Read-only tenant projection adapter with transaction-local user context."""

    def __init__(self, connection: TenantConnection) -> None:
        self._connection = connection

    def projects_for_user(self, user_id: str) -> tuple[TenantProject, ...]:
        """Read ordered project metadata after binding the RLS user setting locally."""

        self._connection.execute(*set_authenticated_user_sql(user_id))
        rows = self._connection.execute(
            """
select project_id::text, user_id::text, name
from portfell_app.projects
where status = 'active'
order by project_id
"""
        ).fetchall()
        return tuple(
            TenantProject(
                project_id=_row_text(row, 0),
                user_id=_row_text(row, 1),
                name=_row_text(row, 2),
            )
            for row in rows
        )


@dataclass(frozen=True)
class ParityMismatch:
    """Redacted mismatch diagnostic that never exposes another user's membership."""

    field: str
    expected_count: int
    actual_count: int


def compare_project_parity(
    expected: tuple[TenantProject, ...], actual: tuple[TenantProject, ...]
) -> tuple[ParityMismatch, ...]:
    """Compare normalized metadata projections without returning tenant values."""

    if expected == actual:
        return ()
    return (ParityMismatch("projects", len(expected), len(actual)),)


class ProjectRepository(Protocol):
    """User-scoped project and current-project preference persistence port."""

    def create_project(self, project: TenantProject) -> TenantProject:
        """Create or return the project identified by its stable command id."""

        ...

    def list_projects(self, user_id: str) -> tuple[TenantProject, ...]:
        """List active projects in deterministic order."""

        ...

    def delete_project(self, *, user_id: str, project_id: str) -> None:
        """Soft-delete one owned project."""

        ...

    def set_current_project(self, *, user_id: str, project_id: str) -> None:
        """Set one owned active project as the user preference."""

        ...

    def current_project_id(self, user_id: str) -> str | None:
        """Return the owned current-project preference when one exists."""

        ...


class InMemoryProjectRepository:
    """Contract test double for user-scoped project commands."""

    def __init__(self) -> None:
        self._projects: dict[str, TenantProject] = {}
        self._deleted_ids: set[str] = set()
        self._current_project_ids: dict[str, str] = {}

    def create_project(self, project: TenantProject) -> TenantProject:
        existing = self._projects.get(project.project_id)
        if existing is not None and existing != project:
            raise TenantImportError("project_command_conflict")
        self._projects[project.project_id] = project
        self._deleted_ids.discard(project.project_id)
        return project

    def list_projects(self, user_id: str) -> tuple[TenantProject, ...]:
        return tuple(
            project
            for project in sorted(self._projects.values())
            if project.user_id == user_id and project.project_id not in self._deleted_ids
        )

    def delete_project(self, *, user_id: str, project_id: str) -> None:
        project = self._projects.get(project_id)
        if project is None or project.user_id != user_id:
            raise TenantImportError("project_not_found")
        self._deleted_ids.add(project_id)
        self._current_project_ids.pop(user_id, None)

    def set_current_project(self, *, user_id: str, project_id: str) -> None:
        if not any(project.project_id == project_id for project in self.list_projects(user_id)):
            raise TenantImportError("project_not_found")
        self._current_project_ids[user_id] = project_id

    def current_project_id(self, user_id: str) -> str | None:
        project_id = self._current_project_ids.get(user_id)
        if project_id is None:
            return None
        return project_id if any(
            project.project_id == project_id for project in self.list_projects(user_id)
        ) else None


class PostgresProjectRepository:
    """Parameterized project adapter; callers provide the command transaction."""

    def __init__(self, connection: TenantConnection) -> None:
        self._connection = connection

    def create_project(self, project: TenantProject) -> TenantProject:
        self._bind_user(project.user_id)
        self._connection.execute(
            """
insert into portfell_app.projects (project_id, user_id, name)
values (%s::uuid, %s::uuid, %s)
on conflict (project_id) do nothing
""",
            (project.project_id, project.user_id, project.name),
        )
        return project

    def list_projects(self, user_id: str) -> tuple[TenantProject, ...]:
        return PostgresTenantProjectionRepository(self._connection).projects_for_user(user_id)

    def delete_project(self, *, user_id: str, project_id: str) -> None:
        self._bind_user(user_id)
        cursor = self._connection.execute(
            """
update portfell_app.projects
set status = 'deleted', deleted_at = now()
where project_id = %s::uuid and status = 'active'
returning project_id
""",
            (project_id,),
        )
        if not cursor.fetchall():
            raise TenantImportError("project_not_found")

    def set_current_project(self, *, user_id: str, project_id: str) -> None:
        self._bind_user(user_id)
        self._connection.execute(
            """
insert into portfell_app.current_project_preferences (user_id, project_id)
values (%s::uuid, %s::uuid)
on conflict (user_id) do update set project_id = excluded.project_id
""",
            (user_id, project_id),
        )

    def current_project_id(self, user_id: str) -> str | None:
        self._bind_user(user_id)
        rows = self._connection.execute(
            """
select preference.project_id::text
from portfell_app.current_project_preferences as preference
join portfell_app.projects as project
  on project.project_id = preference.project_id
where preference.user_id = %s::uuid and project.status = 'active'
""",
            (user_id,),
        ).fetchall()
        if not rows:
            return None
        project_id = rows[0][0]
        if not isinstance(project_id, str) or not project_id:
            raise TenantImportError("current_project_projection_invalid")
        return project_id

    def _bind_user(self, user_id: str) -> None:
        self._connection.execute(*set_authenticated_user_sql(user_id))


class TenantImportCursor(Protocol):
    """Minimal result contract for durable import idempotency checks."""

    def fetchone(self) -> tuple[object, ...] | None: ...


class TenantImportConnection(Protocol):
    """Transactional PostgreSQL boundary for the tenant control-plane importer."""

    def transaction(self) -> AbstractContextManager[object]: ...

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> TenantImportCursor: ...


class PostgresTenantRepository:
    """Persist imported project control metadata with deterministic legacy UUID mapping."""

    def __init__(self, connection: TenantImportConnection) -> None:
        self._connection = connection

    def imported_checksums(self) -> tuple[str, ...]:
        cursor = self._connection.execute(
            "select checksum from portfell_private.legacy_imports order by checksum"
        )
        rows = getattr(cursor, "fetchall", lambda: ())()
        return tuple(str(row[0]) for row in rows)

    def import_snapshot(
        self,
        *,
        checksum: str,
        projects: tuple[TenantProject, ...],
        selections: tuple[TenantSelection, ...],
        current_projects: Mapping[str, str],
    ) -> None:
        with self._connection.transaction():
            cursor = self._connection.execute(
                """
insert into portfell_private.legacy_imports (checksum) values (%s)
on conflict (checksum) do nothing returning checksum
""",
                (checksum,),
            )
            if cursor.fetchone() is None:
                return
            for project in projects:
                user_id = _legacy_uuid(project.user_id)
                project_id = _legacy_uuid(project.project_id)
                self._connection.execute(
                    """
insert into portfell_app.users (user_id, status) values (%s, 'active')
on conflict (user_id) do nothing
""",
                    (user_id,),
                )
                self._connection.execute(
                    """
insert into portfell_app.projects (project_id, user_id, name) values (%s, %s, %s)
on conflict (project_id) do nothing
""",
                    (project_id, user_id, project.name),
                )
            for selection in selections:
                self._insert_selection(selection)
            for user_id, project_id in current_projects.items():
                self._connection.execute(
                    """
insert into portfell_app.current_project_preferences (user_id, project_id)
values (%s, %s)
on conflict (user_id) do update set project_id = excluded.project_id, updated_at = now()
""",
                    (_legacy_uuid(user_id), _legacy_uuid(project_id)),
                )

    def _insert_selection(self, selection: TenantSelection) -> None:
        user_id = _legacy_uuid(selection.user_id)
        project_id = _legacy_uuid(selection.project_id)
        selection_id = _legacy_uuid(selection.selection_id)
        membership_hash = hashlib.sha256("\n".join(selection.member_ids).encode()).hexdigest()
        self._connection.execute(
            """
insert into portfell_app.project_selection_versions (
    selection_version_id, project_id, user_id, name, membership_hash,
    canonical_listing_policy_version
) values (%s, %s, %s, %s, %s, 'legacy-import-v1')
on conflict (project_id) do nothing
""",
            (selection_id, project_id, user_id, selection.name, membership_hash),
        )
        for member_id in selection.member_ids:
            isin, exchange, code = member_id.split(":")
            self._connection.execute(
                """
insert into portfell_app.project_selection_members (
    selection_version_id, project_id, user_id, isin, provider, exchange, code, canonical_listing_id
) values (%s, %s, %s, %s, 'eodhd', %s, %s, %s)
on conflict (selection_version_id, isin) do nothing
""",
                (selection_id, project_id, user_id, isin, exchange, code, member_id),
            )
        self._connection.execute(
            """
update portfell_app.project_selection_versions
set membership_sealed_at = now()
where selection_version_id = %s and membership_sealed_at is null
""",
            (selection_id,),
        )


class InMemoryTenantRepository:
    """Deterministic test double for importer and repository contract tests."""

    def __init__(self) -> None:
        self._projects: tuple[TenantProject, ...] = ()
        self._selections: tuple[TenantSelection, ...] = ()
        self._current_projects: dict[str, str] = {}
        self._checksums: tuple[str, ...] = ()

    @property
    def projects(self) -> tuple[TenantProject, ...]:
        return self._projects

    @property
    def import_checksums(self) -> tuple[str, ...]:
        return self._checksums

    def imported_checksums(self) -> tuple[str, ...]:
        return self._checksums

    def import_snapshot(
        self,
        *,
        checksum: str,
        projects: tuple[TenantProject, ...],
        selections: tuple[TenantSelection, ...],
        current_projects: Mapping[str, str],
    ) -> None:
        if checksum in self._checksums:
            return
        if self._checksums:
            raise TenantImportError("local_workspace_import_checksum_mismatch")
        self._projects = projects
        self._selections = selections
        self._current_projects = dict(current_projects)
        self._checksums = (checksum,)


def import_local_workspace(
    repository: TenantRepository,
    payload: Mapping[str, object],
    *,
    dry_run: bool,
) -> ImportReport:
    """Plan or atomically import validated control metadata without payload rows."""

    projects = _projects(payload.get("projects", ()))
    selections = _selections(payload.get("selections", ()), projects)
    current_projects = _current_projects(payload.get("current_project_id_by_user", {}), projects)
    checksum = _checksum(projects, selections, current_projects)
    report = ImportReport(
        checksum=checksum,
        project_count=len(projects),
        selection_count=len(selections),
        membership_count=sum(len(selection.member_ids) for selection in selections),
        dry_run=dry_run,
    )
    if not dry_run:
        repository.import_snapshot(
            checksum=checksum,
            projects=projects,
            selections=selections,
            current_projects=current_projects,
        )
    return report


def _projects(value: object) -> tuple[TenantProject, ...]:
    rows = _rows(value, "projects")
    projects = tuple(
        sorted(
            (
                TenantProject(
                    project_id=_text(row, "project_id"),
                    user_id=_text(row, "user_id"),
                    name=_text(row, "name"),
                )
                for row in rows
            ),
            key=lambda project: (project.user_id, project.project_id),
        )
    )
    if len({project.project_id for project in projects}) != len(projects):
        raise TenantImportError("local_workspace_duplicate_project")
    return projects


def _selections(value: object, projects: tuple[TenantProject, ...]) -> tuple[TenantSelection, ...]:
    known_projects = {(project.project_id, project.user_id) for project in projects}
    selections: list[TenantSelection] = []
    for row in _rows(value, "selections"):
        project_id = _text(row, "project_id")
        user_id = _text(row, "user_id")
        if (project_id, user_id) not in known_projects:
            raise TenantImportError("local_workspace_selection_owner_mismatch")
        raw_member_values = row.get("member_ids")
        if not isinstance(raw_member_values, list):
            raise TenantImportError("local_workspace_selection_members_invalid")
        member_values = cast(list[object], raw_member_values)
        if not all(isinstance(member, str) and member for member in member_values):
            raise TenantImportError("local_workspace_selection_members_invalid")
        members = tuple(sorted(cast(list[str], member_values)))
        isins = [_member_isin(member) for member in members]
        if len(set(isins)) != len(isins):
            raise TenantImportError("local_workspace_duplicate_selection_isin")
        selections.append(
            TenantSelection(
                _text(row, "selection_id"), project_id, user_id, _text(row, "name"), members
            )
        )
    if len({selection.selection_id for selection in selections}) != len(selections):
        raise TenantImportError("local_workspace_duplicate_selection")
    return tuple(
        sorted(selections, key=lambda selection: (selection.user_id, selection.selection_id))
    )


def _current_projects(value: object, projects: tuple[TenantProject, ...]) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise TenantImportError("local_workspace_current_project_invalid")
    values = cast(Mapping[object, object], value)
    known_projects = {(project.user_id, project.project_id) for project in projects}
    current_projects: dict[str, str] = {}
    for user_id, project_id in values.items():
        if not isinstance(user_id, str) or not isinstance(project_id, str):
            raise TenantImportError("local_workspace_current_project_invalid")
        if (user_id, project_id) not in known_projects:
            raise TenantImportError("local_workspace_current_project_owner_mismatch")
        current_projects[user_id] = project_id
    return dict(sorted(current_projects.items()))


def _rows(value: object, name: str) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        raise TenantImportError(f"local_workspace_{name}_invalid")
    rows = cast(list[object], value)
    if not all(isinstance(row, Mapping) for row in rows):
        raise TenantImportError(f"local_workspace_{name}_invalid")
    return [cast(Mapping[str, object], row) for row in rows]


def _text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise TenantImportError(f"local_workspace_{key}_invalid")
    return value


def _row_text(row: tuple[object, ...], index: int) -> str:
    value = row[index]
    if not isinstance(value, str) or not value:
        raise TenantImportError("postgres_tenant_projection_invalid")
    return value


def _member_isin(member_id: str) -> str:
    parts = member_id.split(":")
    if len(parts) != 3 or not all(parts):
        raise TenantImportError("local_workspace_member_id_invalid")
    return parts[0]


def _checksum(
    projects: tuple[TenantProject, ...],
    selections: tuple[TenantSelection, ...],
    current_projects: Mapping[str, str],
) -> str:
    payload: dict[str, Any] = {
        "projects": [project.__dict__ for project in projects],
        "selections": [selection.__dict__ for selection in selections],
        "current_projects": dict(current_projects),
    }
    return hashlib.sha256(
        json.dumps(payload, default=list, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _legacy_uuid(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"portfell-legacy:{value}"))
