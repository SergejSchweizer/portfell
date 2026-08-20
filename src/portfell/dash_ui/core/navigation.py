"""Deterministic four-stage Dash navigation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from portfell.dash_ui.core.availability import Availability, AvailabilityState
from portfell.dash_ui.core.routes import WORKFLOW_ORDER, WorkflowId, project_route


@dataclass(frozen=True, slots=True)
class NavigationItem:
    workflow: WorkflowId
    label: str
    href: str


@dataclass(frozen=True, slots=True)
class ProjectSwitchDecision:
    project_slug: str | None
    clear_presented_state: bool
    should_read: bool
    availability: Availability


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


def project_switch(
    *,
    current_slug: str | None,
    requested_slug: str,
    available_slugs: Iterable[str],
) -> ProjectSwitchDecision:
    """Resolve project switching without using URL state as authorization."""

    available = frozenset(available_slugs)
    if requested_slug not in available:
        return ProjectSwitchDecision(
            project_slug=None,
            clear_presented_state=True,
            should_read=False,
            availability=Availability(AvailabilityState.UNAVAILABLE, "project_unavailable"),
        )
    if current_slug == requested_slug:
        return ProjectSwitchDecision(
            project_slug=requested_slug,
            clear_presented_state=False,
            should_read=False,
            availability=Availability(AvailabilityState.AVAILABLE),
        )
    return ProjectSwitchDecision(
        project_slug=requested_slug,
        clear_presented_state=True,
        should_read=True,
        availability=Availability(AvailabilityState.AVAILABLE),
    )
