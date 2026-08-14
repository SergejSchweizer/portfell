"""Command-side canonical writer for compact project workflow projections."""

from __future__ import annotations

from collections.abc import Callable

from portfell.hosted_project_workflow_projection_repository import (
    PostgresProjectWorkflowProjection,
)
from portfell.table_io import JsonRow


class PostgresProjectWorkflowProjector:
    """Rebuild and persist one project's workflow only after a command transition."""

    def __init__(
        self,
        workflow_source: Callable[[str, str | None], JsonRow],
        projections: PostgresProjectWorkflowProjection,
    ) -> None:
        self._workflow_source = workflow_source
        self._projections = projections

    def reconcile(self, user_id: str, project_id: str) -> tuple[JsonRow, str]:
        payload = {"schema_version": 1, **self._workflow_source(user_id, project_id)}
        return self._projections.write(user_id=user_id, project_id=project_id, payload=payload)
