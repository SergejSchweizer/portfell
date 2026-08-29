"""Research workflow projection for source-backed Bivariate runs."""

from __future__ import annotations

from typing import cast

from portfell.hosted_api_service_support import opaque_id
from portfell.hosted_postgres_research_repository import PostgresResearchRepository
from portfell.hosted_postgres_workflow import WorkflowResearchState
from portfell.hosted_research_workflow import ResearchRun, univariate_source_id


class BivariateMarketSourcePostgresResearchRepository(PostgresResearchRepository):
    """Resolve Bivariate state from durable project mappings instead of quote-run identity."""

    def workflow_state(
        self, *, user_id: str, project_id: str, metadata_selection_id: str
    ) -> WorkflowResearchState:
        self._bind(user_id)
        univariate_source = univariate_source_id(metadata_selection_id, "shared-market")
        univariate_run_id = opaque_id("univariate-run", f"{user_id}:{univariate_source}")
        univariate = self._run_row(univariate_run_id, "univariate")
        if univariate is None:
            return WorkflowResearchState()
        selection = self._current_selection_for_run(user_id, univariate.run_id)
        if selection is None:
            return WorkflowResearchState(
                univariate_run_id=univariate.run_id,
                univariate_status=univariate.status,
            )
        bivariate = self._latest_project_run(project_id=project_id, kind="bivariate")
        multivariate = (
            None if bivariate is None else self._current_multivariate(project_id, bivariate.run_id)
        )
        return WorkflowResearchState(
            univariate_run_id=univariate.run_id,
            univariate_status=univariate.status,
            univariate_selection_id=selection.selection_id,
            univariate_selected_isins=len(
                {member.split(":", 1)[0] for member in selection.member_ids}
            ),
            bivariate_run_id=None if bivariate is None else bivariate.run_id,
            bivariate_status=None if bivariate is None else bivariate.status,
            multivariate_run_id=None if multivariate is None else multivariate[0],
            multivariate_status=None if multivariate is None else multivariate[1],
        )

    def _latest_project_run(self, *, project_id: str, kind: str) -> ResearchRun | None:
        row = self._connection.execute(
            """
select run.research_run_id
from portfell_app.project_research_run_mappings as mapping
join portfell_app.research_runs as run
  on run.research_run_id = mapping.research_run_id
where mapping.project_id = %s::uuid
  and run.run_kind = %s
order by run.updated_at desc, run.research_run_id desc
limit 1
""",
            (project_id, kind),
        ).fetchone()
        if row is None or len(row) != 1 or not isinstance(row[0], str):
            return None
        return cast(ResearchRun | None, self._run_row(row[0], kind))


__all__ = ["BivariateMarketSourcePostgresResearchRepository"]
