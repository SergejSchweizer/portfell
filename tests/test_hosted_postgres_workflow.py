from __future__ import annotations

from portfell.hosted_postgres_workflow import PostgresWorkflowReader, WorkflowResearchState
from portfell.hosted_repository_importer import TenantSelection


class _Selections:
    def __init__(self, selection: TenantSelection | None) -> None:
        self._selection = selection

    def for_project(self, *, project_id: str, user_id: str) -> TenantSelection | None:
        selection = self._selection
        return (
            selection
            if selection is not None
            and (selection.project_id, selection.user_id) == (project_id, user_id)
            else None
        )


def test_postgres_workflow_unlocks_univariate_for_a_gateway_backed_selection() -> None:
    selection = TenantSelection("selection-1", "project-1", "user-1", "Income", ("IE1:XETRA:AAA",))
    reader = PostgresWorkflowReader(
        selections=_Selections(selection),  # type: ignore[arg-type]
        metadata_rows=lambda: ({"isin": "IE1"}, {"isin": "IE1"}),
    )

    row = reader("user-1", "project-1")

    assert row["stages"]["metadata_builder"]["status"] == "complete"
    assert row["stages"]["univariate_statistics"]["status"] == "ready"
    assert row["process_overview"] == {
        "metadata_downloaded_isins": 1,
        "metadata_builder_isins": 1,
        "univariate_statistics_isins": None,
        "quote_start": None,
        "quote_end": None,
    }


def test_postgres_workflow_projects_persisted_shared_market_research_runs() -> None:
    selection = TenantSelection("selection-1", "project-1", "user-1", "Income", ("IE1:XETRA:AAA",))
    reader = PostgresWorkflowReader(
        selections=_Selections(selection),  # type: ignore[arg-type]
        metadata_rows=lambda: ({"isin": "IE1"},),
        research_state=lambda _user_id, _project_id, _selection_id: WorkflowResearchState(
            univariate_run_id="univariate-1",
            univariate_status="complete",
            univariate_selection_id="univariate-selection-1",
            univariate_selected_isins=1,
            bivariate_run_id="bivariate-1",
            bivariate_status="complete",
            multivariate_run_id="multivariate-1",
            multivariate_status="running",
        ),
    )

    row = reader("user-1", "project-1")

    assert row["stages"]["univariate_statistics"]["status"] == "complete"
    assert row["stages"]["bivariate_statistics"]["status"] == "complete"
    assert row["stages"]["multivariate_statistics"] == {
        "status": "running",
        "metadata_revision_id": "shared-market",
        "metadata_selection_id": "selection-1",
        "univariate_run_id": "univariate-1",
        "univariate_selection_id": "univariate-selection-1",
        "bivariate_run_id": "bivariate-1",
        "multivariate_run_id": "multivariate-1",
    }
    assert row["process_overview"]["univariate_statistics_isins"] == 1


def test_postgres_workflow_projects_selected_quote_coverage_period() -> None:
    selection = TenantSelection("selection-1", "project-1", "user-1", "Income", ("IE1:XETRA:AAA",))

    def quote_period(member_ids: tuple[str, ...]) -> tuple[str | None, str | None]:
        return ("2025-02-01", "2026-05-01") if member_ids == selection.member_ids else (None, None)

    reader = PostgresWorkflowReader(
        selections=_Selections(selection),  # type: ignore[arg-type]
        metadata_rows=lambda: (),
        quote_period=quote_period,
    )

    row = reader("user-1", "project-1")

    assert row["process_overview"]["quote_start"] == "2025-02-01"
    assert row["process_overview"]["quote_end"] == "2026-05-01"
