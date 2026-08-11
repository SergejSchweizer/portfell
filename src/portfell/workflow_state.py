"""Canonical state for the four-module research workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

WorkflowStageId = Literal[
    "metadata_builder",
    "univariate_statistics",
    "bivariate_statistics",
    "multivariate_statistics",
]
WorkflowStatus = Literal["locked", "ready", "running", "complete", "failed", "stale"]

WORKFLOW_STAGE_IDS: tuple[WorkflowStageId, ...] = (
    "metadata_builder",
    "univariate_statistics",
    "bivariate_statistics",
    "multivariate_statistics",
)


@dataclass(frozen=True)
class WorkflowStage:
    """One server-owned workflow stage and its immutable upstream inputs."""

    status: WorkflowStatus
    identifiers: dict[str, str] = field(default_factory=lambda: dict[str, str]())

    def to_row(self) -> dict[str, object]:
        return {"status": self.status, **self.identifiers}


def resolve_workflow(
    *,
    metadata_revision_id: str | None,
    metadata_selection_id: str | None,
    quote_run_id: str | None,
    univariate_run_id: str | None = None,
    univariate_selection_id: str | None = None,
    bivariate_run_id: str | None = None,
    bivariate_status: WorkflowStatus | None = None,
    multivariate_run_id: str | None = None,
    multivariate_status: WorkflowStatus | None = None,
) -> dict[str, dict[str, object]]:
    """Resolve the ordered workflow from immutable records without mutation."""

    stages: dict[str, WorkflowStage] = {
        "metadata_builder": WorkflowStage("ready"),
        "univariate_statistics": WorkflowStage("locked"),
        "bivariate_statistics": WorkflowStage("locked"),
        "multivariate_statistics": WorkflowStage("locked"),
    }
    if not (metadata_revision_id and metadata_selection_id):
        return {stage_id: stages[stage_id].to_row() for stage_id in WORKFLOW_STAGE_IDS}

    metadata_identifiers = {
        "metadata_revision_id": metadata_revision_id,
        "metadata_selection_id": metadata_selection_id,
    }
    if quote_run_id:
        metadata_identifiers["quote_run_id"] = quote_run_id
    stages["metadata_builder"] = WorkflowStage(
        "complete",
        metadata_identifiers,
    )
    stages["univariate_statistics"] = WorkflowStage("ready")
    # Shared-market projects have no user-owned quote run.  Their immutable
    # metadata selection and published market revision are sufficient inputs
    # for a durable univariate run.
    if not univariate_run_id:
        return {stage_id: stages[stage_id].to_row() for stage_id in WORKFLOW_STAGE_IDS}

    univariate_identifiers = {
        "metadata_revision_id": metadata_revision_id,
        "metadata_selection_id": metadata_selection_id,
        "univariate_run_id": univariate_run_id,
    }
    if quote_run_id:
        univariate_identifiers["quote_run_id"] = quote_run_id
    if univariate_selection_id:
        univariate_identifiers["univariate_selection_id"] = univariate_selection_id
    stages["univariate_statistics"] = WorkflowStage("complete", univariate_identifiers)
    if not univariate_selection_id:
        return {stage_id: stages[stage_id].to_row() for stage_id in WORKFLOW_STAGE_IDS}

    stages["bivariate_statistics"] = WorkflowStage("ready")
    if bivariate_run_id:
        resolved_bivariate_status = bivariate_status or "complete"
        bivariate_identifiers = {
            "metadata_revision_id": metadata_revision_id,
            "metadata_selection_id": metadata_selection_id,
            "univariate_run_id": univariate_run_id,
            "univariate_selection_id": univariate_selection_id,
            "bivariate_run_id": bivariate_run_id,
        }
        if quote_run_id:
            bivariate_identifiers["quote_run_id"] = quote_run_id
        stages["bivariate_statistics"] = WorkflowStage(
            resolved_bivariate_status,
            bivariate_identifiers,
        )
        if resolved_bivariate_status == "complete":
            stages["multivariate_statistics"] = WorkflowStage(
                "ready",
                dict(bivariate_identifiers),
            )
            if multivariate_run_id and multivariate_status:
                stages["multivariate_statistics"] = WorkflowStage(
                    multivariate_status,
                    {
                        **stages["multivariate_statistics"].identifiers,
                        "multivariate_run_id": multivariate_run_id,
                    },
                )
    return {stage_id: stages[stage_id].to_row() for stage_id in WORKFLOW_STAGE_IDS}
