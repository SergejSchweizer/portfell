"""PostgreSQL-backed workflow projection for hosted shared-store projects."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from portfell.hosted_selection_repository import SelectionRepository
from portfell.table_io import JsonRow
from portfell.workflow_state import resolve_workflow


@dataclass(frozen=True)
class WorkflowResearchState:
    """Persisted analytical records relevant to one project workflow."""

    univariate_run_id: str | None = None
    univariate_status: Literal["running", "complete", "failed"] | None = None
    univariate_selection_id: str | None = None
    univariate_selected_isins: int | None = None
    bivariate_run_id: str | None = None
    bivariate_status: Literal["running", "complete", "failed"] | None = None
    multivariate_run_id: str | None = None
    multivariate_status: Literal["ready", "running", "complete", "failed", "stale"] | None = None


class PostgresWorkflowReader:
    """Project-scoped workflow status without a local workspace authority."""

    def __init__(
        self,
        *,
        selections: SelectionRepository,
        metadata_rows: Callable[[], tuple[JsonRow, ...]],
        research_state: Callable[[str, str, str], WorkflowResearchState] | None = None,
        quote_period: Callable[[tuple[str, ...]], tuple[str | None, str | None]] | None = None,
    ) -> None:
        self._selections = selections
        self._metadata_rows = metadata_rows
        self._research_state = research_state
        self._quote_period = quote_period

    def __call__(self, user_id: str, project_id: str | None) -> JsonRow:
        metadata_count = len(
            {
                str(row.get("isin", "")).strip()
                for row in self._metadata_rows()
                if str(row.get("isin", "")).strip()
            }
        )
        if project_id is None:
            return {
                "stages": resolve_workflow(
                    metadata_revision_id=None, metadata_selection_id=None, quote_run_id=None
                ),
                "process_overview": {"metadata_downloaded_isins": metadata_count},
            }
        selection = self._selections.for_project(project_id=project_id, user_id=user_id)
        if selection is None:
            return {
                "stages": resolve_workflow(
                    metadata_revision_id=None, metadata_selection_id=None, quote_run_id=None
                ),
                "process_overview": {"metadata_downloaded_isins": metadata_count},
            }
        is_ready = True
        quote_start, quote_end = (
            self._quote_period(selection.member_ids)
            if self._quote_period is not None
            else (None, None)
        )
        research = (
            WorkflowResearchState()
            if not is_ready or self._research_state is None
            else self._research_state(user_id, project_id, selection.selection_id)
        )
        return {
            "stages": resolve_workflow(
                metadata_revision_id="shared-market" if is_ready else None,
                metadata_selection_id=selection.selection_id if is_ready else None,
                quote_run_id=None,
                univariate_run_id=(
                    research.univariate_run_id if research.univariate_status == "complete" else None
                ),
                univariate_selection_id=research.univariate_selection_id,
                bivariate_run_id=research.bivariate_run_id,
                bivariate_status=research.bivariate_status,
                multivariate_run_id=research.multivariate_run_id,
                multivariate_status=research.multivariate_status,
            ),
            "process_overview": {
                "metadata_downloaded_isins": metadata_count,
                "metadata_builder_isins": len(
                    {member.split(":", 1)[0] for member in selection.member_ids}
                ),
                "univariate_statistics_isins": research.univariate_selected_isins,
                "quote_start": quote_start,
                "quote_end": quote_end,
            },
        }
