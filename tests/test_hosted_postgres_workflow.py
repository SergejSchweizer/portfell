from __future__ import annotations

from portfell.hosted_postgres_workflow import PostgresWorkflowReader, WorkflowResearchState
from portfell.hosted_project_bootstrap_repository import DurableProjectBootstrap, InitialFillStatus
from portfell.hosted_repository_importer import TenantSelection
from portfell.project_selection_bootstrap import ProjectBootstrap


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


class _Bootstrap:
    def __init__(self, status: str | None) -> None:
        self._status = status

    def status(self, *, user_id: str, project_id: str) -> InitialFillStatus | None:
        if self._status is None:
            return None
        bootstrap = ProjectBootstrap(
            "bootstrap-1", user_id, project_id, "selection-1", ("IE1:XETRA:AAA",), 1, self._status
        )
        return InitialFillStatus(
            DurableProjectBootstrap(bootstrap, "job-1"), self._status, 1, 1, None
        )


def test_postgres_workflow_unlocks_univariate_only_after_owned_initial_fill() -> None:
    selection = TenantSelection("selection-1", "project-1", "user-1", "Income", ("IE1:XETRA:AAA",))
    reader = PostgresWorkflowReader(
        selections=_Selections(selection),  # type: ignore[arg-type]
        bootstrap=_Bootstrap("ready"),  # type: ignore[arg-type]
        metadata_rows=lambda: ({"isin": "IE1"}, {"isin": "IE1"}),
    )

    row = reader("user-1", "project-1")

    assert row["stages"]["metadata_builder"]["status"] == "complete"
    assert row["stages"]["univariate_statistics"]["status"] == "ready"
    assert row["process_overview"] == {
        "metadata_downloaded_isins": 1,
        "metadata_builder_isins": 1,
        "univariate_statistics_isins": None,
    }


def test_postgres_workflow_keeps_statistics_locked_while_initial_fill_is_pending() -> None:
    selection = TenantSelection("selection-1", "project-1", "user-1", "Income", ("IE1:XETRA:AAA",))
    reader = PostgresWorkflowReader(
        selections=_Selections(selection),  # type: ignore[arg-type]
        bootstrap=_Bootstrap("running"),  # type: ignore[arg-type]
        metadata_rows=lambda: (),
    )

    row = reader("user-1", "project-1")

    assert row["stages"]["metadata_builder"]["status"] == "ready"
    assert row["stages"]["univariate_statistics"]["status"] == "locked"


def test_postgres_workflow_projects_persisted_shared_market_research_runs() -> None:
    selection = TenantSelection("selection-1", "project-1", "user-1", "Income", ("IE1:XETRA:AAA",))
    reader = PostgresWorkflowReader(
        selections=_Selections(selection),  # type: ignore[arg-type]
        bootstrap=_Bootstrap("ready"),  # type: ignore[arg-type]
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
