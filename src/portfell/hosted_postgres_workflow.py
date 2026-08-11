"""PostgreSQL-backed workflow projection for hosted shared-store projects."""

from __future__ import annotations

from collections.abc import Callable

from portfell.hosted_project_bootstrap_repository import ProjectBootstrapRepository
from portfell.hosted_selection_repository import SelectionRepository
from portfell.table_io import JsonRow
from portfell.workflow_state import resolve_workflow


class PostgresWorkflowReader:
    """Project-scoped workflow status without a local workspace authority."""

    def __init__(
        self,
        *,
        selections: SelectionRepository,
        bootstrap: ProjectBootstrapRepository,
        metadata_rows: Callable[[], tuple[JsonRow, ...]],
    ) -> None:
        self._selections = selections
        self._bootstrap = bootstrap
        self._metadata_rows = metadata_rows

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
        fill = self._bootstrap.status(user_id=user_id, project_id=project_id)
        is_ready = fill is not None and fill.status == "ready"
        return {
            "stages": resolve_workflow(
                metadata_revision_id="shared-market" if is_ready else None,
                metadata_selection_id=selection.selection_id if is_ready else None,
                quote_run_id=None,
            ),
            "process_overview": {
                "metadata_downloaded_isins": metadata_count,
                "metadata_builder_isins": len(
                    {member.split(":", 1)[0] for member in selection.member_ids}
                ),
                "univariate_statistics_isins": None,
            },
        }
