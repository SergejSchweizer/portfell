"""Credential, basic download, dataset, and account route registration."""

# pyright: reportUnusedFunction=false
# ruff: noqa: B008

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Header

from portfell.hosted_api_contracts import CredentialSetRequest, DownloadRequest
from portfell.hosted_api_state import ApiUser
from portfell.hosted_credential_project_service import CredentialProjectService
from portfell.hosted_routes_common import JsonRow, call


def credential_router(
    service: CredentialProjectService,
    *,
    current_user: Callable[[], ApiUser],
    workspace_user: Callable[[], ApiUser],
) -> APIRouter:
    """Build credential and account routes around an application service."""

    router = APIRouter()

    @router.get("/credentials/eodhd")
    def credential_status(user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.credential_status, user.user_id)

    @router.post("/credentials/eodhd")
    def set_credential(
        payload: CredentialSetRequest,
        user: ApiUser = Depends(workspace_user),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JsonRow:
        return call(
            service.set_credential,
            user.user_id,
            payload.provider_key,
            idempotency_key,
        )

    @router.delete("/credentials/eodhd")
    def delete_credential(user: ApiUser = Depends(workspace_user)) -> JsonRow:
        return call(service.delete_credential, user.user_id)

    @router.post("/downloads/plan")
    def plan_download(payload: DownloadRequest, user: ApiUser = Depends(workspace_user)) -> JsonRow:
        return call(service.plan_download, user.user_id, payload.symbols)

    @router.post("/downloads/run")
    def run_download(
        payload: DownloadRequest,
        user: ApiUser = Depends(workspace_user),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JsonRow:
        return call(service.run_download, user.user_id, payload.symbols, idempotency_key)

    @router.get("/downloads/{download_run_id}")
    def download_status(download_run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.download_status, user.user_id, download_run_id)

    @router.get("/datasets")
    def visible_datasets(user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.visible_datasets, user.user_id)

    @router.delete("/account")
    def delete_account(user: ApiUser = Depends(workspace_user)) -> JsonRow:
        return call(service.delete_account, user.user_id)

    return router
