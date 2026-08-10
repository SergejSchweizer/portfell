"""Local-only project repository adapter for the hosted development runtime."""

from __future__ import annotations

from portfell.hosted_api_state import HostedApiState, ProjectRecord
from portfell.hosted_repository_importer import (
    ProjectRepository,
    TenantImportError,
    TenantProject,
)


class LocalProjectRepository(ProjectRepository):
    """Persist local-mode project state in the explicit development-state adapter."""

    def __init__(self, state: HostedApiState) -> None:
        self._state = state

    def create_project(self, project: TenantProject) -> TenantProject:
        existing = self._state.projects_by_id.get(project.project_id)
        record = ProjectRecord(project.project_id, project.user_id, project.name)
        if existing is not None and existing != record:
            raise TenantImportError("project_command_conflict")
        self._state.projects_by_id[project.project_id] = record
        return project

    def list_projects(self, user_id: str) -> tuple[TenantProject, ...]:
        return tuple(
            TenantProject(project.project_id, project.user_id, project.name)
            for project in self._state.projects_by_id.values()
            if project.user_id == user_id
        )

    def delete_project(self, *, user_id: str, project_id: str) -> None:
        project = self._state.projects_by_id.get(project_id)
        if project is None or project.user_id != user_id:
            raise TenantImportError("project_not_found")
        self._state.projects_by_id.pop(project_id)
        if self._state.current_project_id_by_user.get(user_id) == project_id:
            self._state.current_project_id_by_user.pop(user_id, None)

    def set_current_project(self, *, user_id: str, project_id: str) -> None:
        project = self._state.projects_by_id.get(project_id)
        if project is None or project.user_id != user_id:
            raise TenantImportError("project_not_found")
        self._state.current_project_id_by_user[user_id] = project_id

    def current_project_id(self, user_id: str) -> str | None:
        project_id = self._state.current_project_id_by_user.get(user_id)
        project = self._state.projects_by_id.get(project_id) if project_id else None
        return project_id if project is not None and project.user_id == user_id else None
