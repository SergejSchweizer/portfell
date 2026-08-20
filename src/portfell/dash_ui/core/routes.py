"""Frozen workflow route registry for the Dash replacement UI."""

from __future__ import annotations

from enum import StrEnum


class WorkflowId(StrEnum):
    """The only browser workflow stages supported by Portfell."""

    METADATA_BUILDER = "metadata_builder"
    UNIVARIATE_STATISTICS = "univariate_statistics"
    BIVARIATE_STATISTICS = "bivariate_statistics"
    MULTIVARIATE_STATISTICS = "multivariate_statistics"


WORKFLOW_ORDER: tuple[WorkflowId, ...] = (
    WorkflowId.METADATA_BUILDER,
    WorkflowId.UNIVARIATE_STATISTICS,
    WorkflowId.BIVARIATE_STATISTICS,
    WorkflowId.MULTIVARIATE_STATISTICS,
)

WORKFLOW_SUFFIX: dict[WorkflowId, str] = {
    WorkflowId.METADATA_BUILDER: "/metadata-builder",
    WorkflowId.UNIVARIATE_STATISTICS: "/univariate-statistics",
    WorkflowId.BIVARIATE_STATISTICS: "/bivariate-statistics",
    WorkflowId.MULTIVARIATE_STATISTICS: "/multivariate-statistics",
}

TEMPORARY_DASH_PREFIX = "/dash"
PRODUCTION_DASH_PREFIX = ""


def normalize_base_prefix(base_prefix: str) -> str:
    """Return the only accepted temporary or production base prefix."""

    candidate = base_prefix.rstrip("/")
    if candidate not in {TEMPORARY_DASH_PREFIX, PRODUCTION_DASH_PREFIX}:
        raise ValueError("Dash base prefix must be '/dash' or root")
    return candidate


def project_route(*, project_slug: str, workflow: WorkflowId, base_prefix: str) -> str:
    """Build one canonical project route from the frozen registry."""

    if not project_slug or "/" in project_slug:
        raise ValueError("project_slug must be a non-empty path segment")
    prefix = normalize_base_prefix(base_prefix)
    return f"{prefix}/projects/{project_slug}{WORKFLOW_SUFFIX[workflow]}"
