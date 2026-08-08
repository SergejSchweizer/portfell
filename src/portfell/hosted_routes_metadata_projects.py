"""Metadata, project, workflow, and selection route registration."""

# pyright: reportUnusedFunction=false
# ruff: noqa: B008

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, Header

from portfell.hosted_api_contracts import (
    CurrentProjectRequest,
    MetadataFilterProjectRequest,
    ProjectCreateRequest,
    SelectionCreateRequest,
    UnivariateSelectionSettingsRequest,
)
from portfell.hosted_api_state import ApiUser
from portfell.hosted_credential_project_service import CredentialProjectService
from portfell.hosted_metadata_project_service import MetadataProjectService
from portfell.hosted_routes_common import JsonRow, call


def metadata_project_router(
    projects: CredentialProjectService,
    metadata: MetadataProjectService,
    *,
    current_user: Callable[[], ApiUser],
    workspace_user: Callable[[], ApiUser],
) -> APIRouter:
    """Build metadata and project routes around application services."""

    router = APIRouter()

    @router.get("/health")
    def health() -> JsonRow:
        return {"status": "ok"}

    @router.get("/workflow")
    def workflow(user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(projects.workflow, user.user_id)

    @router.get("/projects/{project_id}/workflow")
    def project_workflow(project_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(projects.workflow, user.user_id, project_id)

    @router.post("/projects")
    def create_project(
        payload: ProjectCreateRequest,
        user: ApiUser = Depends(workspace_user),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JsonRow:
        return call(projects.create_project, user.user_id, payload.name, idempotency_key)

    @router.get("/projects")
    def list_projects(
        user: ApiUser = Depends(current_user), limit: int = 100, offset: int = 0
    ) -> JsonRow:
        return call(projects.list_projects, user.user_id, limit, offset)

    @router.get("/project-context")
    def project_context(user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(projects.project_context, user.user_id)

    @router.put("/project-context/current-project")
    def select_current_project(
        payload: CurrentProjectRequest, user: ApiUser = Depends(workspace_user)
    ) -> JsonRow:
        return call(projects.select_current_project, user.user_id, payload.project_id)

    @router.get("/projects/{project_id}/metadata-filter")
    def project_metadata_filter(project_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        project, selection = call(projects.project_metadata_filter, user.user_id, project_id)
        return call(metadata.project_filter_row, project, selection)

    @router.get("/projects/{project_id}/univariate-selection-settings")
    def univariate_selection_settings(
        project_id: str, user: ApiUser = Depends(current_user)
    ) -> JsonRow:
        return call(projects.univariate_selection_settings, user.user_id, project_id)

    @router.put("/projects/{project_id}/univariate-selection-settings")
    def save_univariate_selection_settings(
        project_id: str,
        payload: UnivariateSelectionSettingsRequest,
        user: ApiUser = Depends(workspace_user),
    ) -> JsonRow:
        return call(
            projects.save_univariate_selection_settings,
            user.user_id,
            project_id,
            payload.model_dump(mode="json"),
        )

    @router.delete("/projects/{project_id}")
    def delete_project(project_id: str, user: ApiUser = Depends(workspace_user)) -> JsonRow:
        return call(projects.delete_project, user.user_id, project_id)

    @router.get("/metadata-filter/options")
    def metadata_filter_options(user: ApiUser = Depends(current_user)) -> JsonRow:
        _ = user
        return call(metadata.options)

    @router.post("/metadata/fetch-all")
    def fetch_all_metadata(
        background_tasks: BackgroundTasks,
        user: ApiUser = Depends(workspace_user),
    ) -> JsonRow:
        row, task = call(metadata.start_metadata_fetch, user.user_id)
        background_tasks.add_task(task)
        return row

    @router.get("/metadata/fetch-all/{metadata_run_id}")
    def metadata_fetch_status(
        metadata_run_id: str, user: ApiUser = Depends(workspace_user)
    ) -> JsonRow:
        return call(metadata.metadata_fetch_status, user.user_id, metadata_run_id)

    @router.post("/metadata-filter")
    def create_metadata_filter_project(
        payload: MetadataFilterProjectRequest,
        user: ApiUser = Depends(workspace_user),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JsonRow:
        return call(
            metadata.create_filter_project,
            user.user_id,
            exchange=payload.exchange,
            name=payload.name,
            instrument_type=payload.instrument_type,
            country=payload.country,
            currency=payload.currency,
            idempotency_key=idempotency_key,
        )

    @router.post("/selections")
    def create_selection(
        payload: SelectionCreateRequest, user: ApiUser = Depends(workspace_user)
    ) -> JsonRow:
        return call(
            projects.create_selection,
            user.user_id,
            payload.project_id,
            payload.name,
            payload.member_ids,
        )

    @router.get("/selections/{selection_id}")
    def selection_detail(selection_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(projects.selection_detail, user.user_id, selection_id)

    return router
