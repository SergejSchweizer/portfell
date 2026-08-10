"""D017 tenant repository ports and read-only local-workspace importer."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast


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
