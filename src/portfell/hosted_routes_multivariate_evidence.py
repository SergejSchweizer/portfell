"""Read-only FastAPI router for persisted Multivariate decision/history evidence."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from fastapi import APIRouter, HTTPException


class MultivariateEvidenceReader(Protocol):
    def run_projection(
        self, *, user_id: str, project_slug: str, run_id: str
    ) -> Mapping[str, object]: ...

    def section_projection(
        self,
        *,
        user_id: str,
        project_slug: str,
        run_id: str,
        section_id: str,
    ) -> Mapping[str, object]: ...

    def pipeline_projection(
        self, *, user_id: str, project_slug: str, run_id: str
    ) -> tuple[Mapping[str, object], ...]: ...


class CurrentApiUser(Protocol):
    user_id: str


def multivariate_evidence_router(
    reader: MultivariateEvidenceReader,
    *,
    current_user: Callable[[], CurrentApiUser],
) -> APIRouter:
    """Create GET-only routes; authorization remains in the reader/project resolver."""

    router = APIRouter(
        prefix="/api/projects/{project_slug}/multivariate",
        tags=["multivariate-evidence"],
    )

    @router.get("/runs/{run_id}/evidence")
    def read_run(project_slug: str, run_id: str) -> Mapping[str, object]:
        try:
            return reader.run_projection(
                user_id=current_user().user_id,
                project_slug=project_slug,
                run_id=run_id,
            )
        except (KeyError, PermissionError) as exc:
            raise HTTPException(
                status_code=404,
                detail="multivariate_evidence_unavailable",
            ) from exc

    @router.get("/runs/{run_id}/sections/{section_id}")
    def read_section(
        project_slug: str,
        run_id: str,
        section_id: str,
    ) -> Mapping[str, object]:
        try:
            return reader.section_projection(
                user_id=current_user().user_id,
                project_slug=project_slug,
                run_id=run_id,
                section_id=section_id,
            )
        except (KeyError, PermissionError) as exc:
            raise HTTPException(
                status_code=404,
                detail="multivariate_section_unavailable",
            ) from exc

    @router.get("/runs/{run_id}/universe-history")
    def read_pipeline(
        project_slug: str,
        run_id: str,
    ) -> tuple[Mapping[str, object], ...]:
        try:
            return reader.pipeline_projection(
                user_id=current_user().user_id,
                project_slug=project_slug,
                run_id=run_id,
            )
        except (KeyError, PermissionError) as exc:
            raise HTTPException(
                status_code=404,
                detail="multivariate_history_unavailable",
            ) from exc

    return router
