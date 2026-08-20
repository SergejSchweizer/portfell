"""Deterministic four-stage Dash navigation."""

from __future__ import annotations

from dataclasses import dataclass

from portfell.dash_ui.core.routes import WORKFLOW_ORDER, WorkflowId, project_route


@dataclass(frozen=True, slots=True)
class NavigationItem:
    workflow: WorkflowId
    label: str
    href: str


WORKFLOW_LABELS: dict[WorkflowId, str] = {
    WorkflowId.METADATA_BUILDER: "Metadata Builder",
    WorkflowId.UNIVARIATE_STATISTICS: "Univariate Statistics",
    WorkflowId.BIVARIATE_STATISTICS: "Bivariate Statistics",
    WorkflowId.MULTIVARIATE_STATISTICS: "Multivariate Statistics",
}


def navigation_items(*, project_slug: str, base_prefix: str) -> tuple[NavigationItem, ...]:
    """Return exactly four links in frozen workflow order."""

    return tuple(
        NavigationItem(
            workflow=workflow,
            label=WORKFLOW_LABELS[workflow],
            href=project_route(
                project_slug=project_slug,
                workflow=workflow,
                base_prefix=base_prefix,
            ),
        )
        for workflow in WORKFLOW_ORDER
    )
