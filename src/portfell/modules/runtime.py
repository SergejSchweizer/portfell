"""Runtime-enforced service capabilities for each feature module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ModuleBoundaryError(AttributeError):
    """Raised when a module attempts to use a capability it does not own."""


class ModuleService:
    """Expose only explicitly assigned application-service operations."""

    __slots__ = ("_delegate", "_module", "_operations")

    def __init__(self, module: str, delegate: object, operations: frozenset[str]) -> None:
        self._module = module
        self._delegate = delegate
        self._operations = operations

    def __getattr__(self, name: str) -> Any:
        if name not in self._operations:
            raise ModuleBoundaryError(f"{self._module}_module_operation_forbidden:{name}")
        return getattr(self._delegate, name)


_METADATA = frozenset(
    {
        "workflow_state",
        "metadata_options",
        "active_listings",
        "metadata_date_range",
        "metadata_universe",
        "metadata_history",
        "create_metadata_universe",
        "create_universe_and_start_univariate",
        "save_metadata_filter_preferences",
    }
)
_UNIVARIATE = frozenset(
    {
        "workflow_state",
        "run_univariate",
        "start_univariate_job",
        "create_univariate_selection",
        "save_univariate_filter_preferences",
        "univariate_summary",
        "univariate_page",
        "univariate_chart_sample",
        "univariate_result_preview",
        "univariate_metric_distributions",
        "run_detail",
        "stage_history",
    }
)
_BIVARIATE = frozenset(
    {
        "workflow_state",
        "run_bivariate",
        "start_bivariate_job",
        "bivariate_summary",
        "bivariate_page",
        "bivariate_chart_sample",
        "run_detail",
        "stage_history",
    }
)
_MULTIVARIATE = frozenset(
    {
        "workflow_state",
        "run_multivariate",
        "start_multivariate_job",
        "multivariate_summary",
        "multivariate_artifact",
        "run_detail",
        "univariate_chart_sample",
        "stage_history",
    }
)
_WORKFLOW = frozenset(
    {
        "workflow_state",
        "active_listings",
        "active_analysis_job",
        "analysis_job_status",
        "create_universe_and_start_univariate",
        "create_metadata_universe",
        "save_metadata_filter_preferences",
        "start_univariate_job",
        "create_univariate_selection",
        "create_selection_and_start_downstream",
        "run_bivariate",
        "start_bivariate_job",
        "run_multivariate",
        "start_multivariate_job",
        "univariate_summary",
        "univariate_page",
        "univariate_chart_sample",
        "univariate_result_preview",
        "univariate_metric_distributions",
    }
)


@dataclass(frozen=True, slots=True)
class ModuleRegistry:
    metadata: ModuleService
    univariate: ModuleService
    bivariate: ModuleService
    multivariate: ModuleService
    workflow: ModuleService

    def page_service(self, page_id: str) -> ModuleService:
        if page_id not in {"metadata", "univariate", "bivariate", "multivariate"}:
            raise ModuleBoundaryError(f"unknown_module:{page_id}")
        return getattr(self, page_id)


def build_module_registry(service: object) -> ModuleRegistry:
    return ModuleRegistry(
        metadata=ModuleService("metadata", service, _METADATA),
        univariate=ModuleService("univariate", service, _UNIVARIATE),
        bivariate=ModuleService("bivariate", service, _BIVARIATE),
        multivariate=ModuleService("multivariate", service, _MULTIVARIATE),
        workflow=ModuleService("workflow", service, _WORKFLOW),
    )
