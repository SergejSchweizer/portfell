"""Authorized persisted-evidence reader used by hosted GET routes."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from portfell.hosted_catalog_ports import CatalogConnection
from portfell.multivariate.read_api.projections import (
    MultivariateEvidenceProjection,
    current_selection_projection,
    pipeline_projection,
    project_run_evidence,
    section_projection,
)

ProjectResolver = Callable[[str, str], str]


class PersistedMultivariateEvidenceReader:
    """Resolve project ownership first, then decode only immutable stored evidence."""

    def __init__(
        self,
        connection: CatalogConnection,
        *,
        resolve_project_id: ProjectResolver,
    ) -> None:
        self._connection = connection
        self._resolve_project_id = resolve_project_id

    def _project_id(self, *, user_id: str, project_slug: str) -> str:
        return self._resolve_project_id(user_id, project_slug)

    def _projection(
        self,
        *,
        user_id: str,
        project_slug: str,
        run_id: str,
    ) -> MultivariateEvidenceProjection:
        project_id = self._project_id(user_id=user_id, project_slug=project_slug)
        return project_run_evidence(
            self._connection,
            user_id=user_id,
            project_slug=project_slug,
            run_id=run_id,
            resolve_project_id=lambda _: project_id,
        )

    def current_projection(
        self,
        *,
        user_id: str,
        project_slug: str,
    ) -> Mapping[str, object]:
        project_id = self._project_id(user_id=user_id, project_slug=project_slug)
        return current_selection_projection(
            self._connection,
            user_id=user_id,
            project_slug=project_slug,
            resolve_project_id=lambda _: project_id,
        )

    def run_projection(
        self, *, user_id: str, project_slug: str, run_id: str
    ) -> Mapping[str, object]:
        projection = self._projection(
            user_id=user_id,
            project_slug=project_slug,
            run_id=run_id,
        )
        return {
            "project_slug": projection.project_slug,
            "run_id": projection.run_id,
            "decisions": projection.decisions,
            "history": projection.history,
        }

    def section_projection(
        self,
        *,
        user_id: str,
        project_slug: str,
        run_id: str,
        section_id: str,
    ) -> Mapping[str, object]:
        projection = self._projection(
            user_id=user_id,
            project_slug=project_slug,
            run_id=run_id,
        )
        return section_projection(projection, section_id=section_id)

    def pipeline_projection(
        self, *, user_id: str, project_slug: str, run_id: str
    ) -> tuple[Mapping[str, object], ...]:
        projection = self._projection(
            user_id=user_id,
            project_slug=project_slug,
            run_id=run_id,
        )
        return pipeline_projection(projection)
