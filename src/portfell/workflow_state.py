"""Canonical state for the four-page research workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

WorkflowStageId = Literal[
    "metadata_filter",
    "univariate_statistics",
    "univariate_filter",
    "bivariate_statistics",
]
WorkflowStatus = Literal["locked", "ready", "running", "complete", "failed", "stale"]

WORKFLOW_STAGE_IDS: tuple[WorkflowStageId, ...] = (
    "metadata_filter",
    "univariate_statistics",
    "univariate_filter",
    "bivariate_statistics",
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
    univariate_filter_selection_id: str | None = None,
    bivariate_run_id: str | None = None,
) -> dict[str, dict[str, object]]:
    """Resolve the ordered workflow from immutable records without mutation."""

    stages: dict[str, WorkflowStage] = {
        "metadata_filter": WorkflowStage("ready"),
        "univariate_statistics": WorkflowStage("locked"),
        "univariate_filter": WorkflowStage("locked"),
        "bivariate_statistics": WorkflowStage("locked"),
    }
    if not (metadata_revision_id and metadata_selection_id and quote_run_id):
        return {stage_id: stages[stage_id].to_row() for stage_id in WORKFLOW_STAGE_IDS}

    stages["metadata_filter"] = WorkflowStage(
        "complete",
        {
            "metadata_revision_id": metadata_revision_id,
            "metadata_selection_id": metadata_selection_id,
            "quote_run_id": quote_run_id,
        },
    )
    stages["univariate_statistics"] = WorkflowStage("ready")
    if not univariate_run_id:
        return {stage_id: stages[stage_id].to_row() for stage_id in WORKFLOW_STAGE_IDS}

    stages["univariate_statistics"] = WorkflowStage(
        "complete",
        {
            "metadata_revision_id": metadata_revision_id,
            "metadata_selection_id": metadata_selection_id,
            "quote_run_id": quote_run_id,
            "univariate_run_id": univariate_run_id,
        },
    )
    stages["univariate_filter"] = WorkflowStage("ready")
    if not univariate_filter_selection_id:
        return {stage_id: stages[stage_id].to_row() for stage_id in WORKFLOW_STAGE_IDS}

    stages["univariate_filter"] = WorkflowStage(
        "complete",
        {
            "metadata_revision_id": metadata_revision_id,
            "metadata_selection_id": metadata_selection_id,
            "quote_run_id": quote_run_id,
            "univariate_run_id": univariate_run_id,
            "univariate_filter_selection_id": univariate_filter_selection_id,
        },
    )
    stages["bivariate_statistics"] = WorkflowStage("ready")
    if bivariate_run_id:
        stages["bivariate_statistics"] = WorkflowStage(
            "complete",
            {
                "metadata_revision_id": metadata_revision_id,
                "metadata_selection_id": metadata_selection_id,
                "quote_run_id": quote_run_id,
                "univariate_run_id": univariate_run_id,
                "univariate_filter_selection_id": univariate_filter_selection_id,
                "bivariate_run_id": bivariate_run_id,
            },
        )
    return {stage_id: stages[stage_id].to_row() for stage_id in WORKFLOW_STAGE_IDS}
