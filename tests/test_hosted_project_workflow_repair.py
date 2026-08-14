from __future__ import annotations

from contextlib import nullcontext

import pytest

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_project_workflow_projection_repository import ABSENT_PROJECT
from portfell.hosted_project_workflow_repair import (
    PostgresProjectWorkflowRepair,
    WorkflowRepairRequest,
)


class _Connection:
    def __init__(self) -> None:
        self.transactions = 0

    def transaction(self) -> object:
        self.transactions += 1
        return nullcontext()


class _Projections:
    def __init__(self, values: dict[tuple[str, str], object]) -> None:
        self.values = values
        self.reads: list[tuple[str, str]] = []

    def read_owned(self, *, user_id: str, project_id: str) -> object:
        self.reads.append((user_id, project_id))
        return self.values.get((user_id, project_id), ABSENT_PROJECT)


class _Projector:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def reconcile(self, user_id: str, project_id: str) -> tuple[dict[str, object], str]:
        self.calls.append((user_id, project_id))
        return {"schema_version": 1, "project_id": project_id}, f"etag:{project_id}"


def test_workflow_repair_only_reconciles_the_explicit_owned_project() -> None:
    connection = _Connection()
    projections = _Projections({("user-a", "project-a"): None})
    projector = _Projector()
    repair = PostgresProjectWorkflowRepair(connection, projections, projector)  # type: ignore[arg-type]

    row, etag = repair.repair(WorkflowRepairRequest("user-a", "project-a"))

    assert row["project_id"] == "project-a"
    assert etag == "etag:project-a"
    assert connection.transactions == 1
    assert projections.reads == [("user-a", "project-a")]
    assert projector.calls == [("user-a", "project-a")]


def test_workflow_repair_skips_absent_projects_without_cross_tenant_reconciliation() -> None:
    connection = _Connection()
    projections = _Projections({("user-a", "project-a"): None})
    projector = _Projector()
    repair = PostgresProjectWorkflowRepair(connection, projections, projector)  # type: ignore[arg-type]

    with pytest.raises(HostedApplicationError, match="not_found"):
        repair.repair(WorkflowRepairRequest("user-b", "project-a"))
    repaired = repair.repair_many(
        (WorkflowRepairRequest("user-b", "project-a"), WorkflowRepairRequest("user-a", "project-a"))
    )

    assert [request for request, _, _ in repaired] == [WorkflowRepairRequest("user-a", "project-a")]
    assert projector.calls == [("user-a", "project-a")]
