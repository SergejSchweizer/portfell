"""Command-side canonical writer for compact project workflow projections."""

from __future__ import annotations

from collections.abc import Callable

from portfell.hosted_project_workflow_projection_repository import (
    PostgresProjectWorkflowProjection,
)
from portfell.hosted_status_event_repository import PostgresStatusEventRepository
from portfell.table_io import JsonRow


class PostgresProjectWorkflowProjector:
    """Rebuild and persist one project's workflow only after a command transition."""

    def __init__(
        self,
        workflow_source: Callable[[str, str | None], JsonRow],
        projections: PostgresProjectWorkflowProjection,
        status_events: PostgresStatusEventRepository | None = None,
    ) -> None:
        self._workflow_source = workflow_source
        self._projections = projections
        self._status_events = status_events

    def reconcile(self, user_id: str, project_id: str) -> tuple[JsonRow, str]:
        payload = {"schema_version": 1, **self._workflow_source(user_id, project_id)}
        written, revision, changed = self._projections.write_with_change(
            user_id=user_id, project_id=project_id, payload=payload
        )
        if changed and self._status_events is not None:
            self._status_events.append(
                user_id=user_id,
                project_id=project_id,
                event_type="workflow.changed",
                aggregate_ref=f"project:{project_id}",
                projection_revision=revision,
            )
        return written, revision
