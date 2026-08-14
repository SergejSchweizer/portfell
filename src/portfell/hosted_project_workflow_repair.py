"""Explicit transactional maintenance repair for project workflow projections."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_project_workflow_projection_repository import (
    ABSENT_PROJECT,
    PostgresProjectWorkflowProjection,
)
from portfell.hosted_project_workflow_projector import PostgresProjectWorkflowProjector
from portfell.table_io import JsonRow


class WorkflowRepairConnection(Protocol):
    def transaction(self) -> AbstractContextManager[object]: ...


@dataclass(frozen=True)
class WorkflowRepairRequest:
    """One explicit tenant/project pair accepted by maintenance tooling."""

    user_id: str
    project_id: str


class PostgresProjectWorkflowRepair:
    """Repair only explicitly named, owned projects in caller-owned PostgreSQL state."""

    def __init__(
        self,
        connection: WorkflowRepairConnection,
        projections: PostgresProjectWorkflowProjection,
        projector: PostgresProjectWorkflowProjector,
    ) -> None:
        self._connection = connection
        self._projections = projections
        self._projector = projector

    def repair(self, request: WorkflowRepairRequest) -> tuple[JsonRow, str]:
        """Rebuild one owned projection in one transaction or return typed absence."""

        with self._connection.transaction():
            owned = self._projections.read_owned(
                user_id=request.user_id, project_id=request.project_id
            )
            if owned is ABSENT_PROJECT:
                raise HostedApplicationError(404, "not_found")
            return self._projector.reconcile(request.user_id, request.project_id)

    def repair_many(
        self, requests: tuple[WorkflowRepairRequest, ...]
    ) -> tuple[tuple[WorkflowRepairRequest, JsonRow, str], ...]:
        """Repair an explicit deterministic request list without tenant enumeration."""

        repaired: list[tuple[WorkflowRepairRequest, JsonRow, str]] = []
        for request in requests:
            try:
                payload, etag = self.repair(request)
            except HostedApplicationError as error:
                if error.status_code != 404:
                    raise
                continue
            repaired.append((request, payload, etag))
        return tuple(repaired)
