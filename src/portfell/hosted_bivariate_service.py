"""Bivariate run application service."""

from __future__ import annotations

from dataclasses import replace

from portfell.bivariate_views import (
    build_bivariate_summary,
    build_correlation_matrix,
    build_covariance_matrix,
)
from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_serializers import research_run_row
from portfell.hosted_api_service_support import opaque_id
from portfell.hosted_research_ports import (
    ResearchDataPort,
    ResearchPersistencePort,
    ResearchRunRepository,
)
from portfell.hosted_research_workflow import (
    HostedResearchError,
    ResearchRun,
    bivariate_source_id,
    create_bivariate_run,
    page_rows,
    pair_plan,
)
from portfell.table_io import JsonRow


class BivariateResearchService:
    """Own bivariate execution while delegating storage and read-model calculations."""

    def __init__(
        self,
        repository: ResearchRunRepository,
        data: ResearchDataPort,
        persistence: ResearchPersistencePort,
    ) -> None:
        self._repository = repository
        self._data = data
        self._persistence = persistence

    def plan(self, user_id: str, selection_id: str) -> JsonRow:
        return pair_plan(self._repository.univariate_selection(selection_id, user_id))

    def start(self, user_id: str, selection_id: str) -> JsonRow:
        selection = self._repository.univariate_selection(selection_id, user_id)
        plan = pair_plan(selection)
        if not plan["allowed"]:
            raise HostedApplicationError(422, "pair_plan_not_runnable")
        source = bivariate_source_id(selection)
        run_id = opaque_id("bivariate-run", f"{user_id}:{source}")
        existing = self._repository.find_bivariate_run(run_id)
        if existing is not None and existing.status != "failed":
            return research_run_row(existing)
        run = ResearchRun(
            run_id=run_id,
            user_id=user_id,
            source_id=source,
            status="running",
            rows=(),
            total=int(plan["theoretical_pair_count"]),
            completed=0,
        )
        self._repository.save_bivariate_run(run)
        self._repository.audit(user_id, "bivariate_statistics.start")
        return research_run_row(run)

    def complete(self, user_id: str, selection_id: str) -> None:
        """Compute every bivariate statistic in the background using all CPU cores."""

        selection = self._repository.univariate_selection(selection_id, user_id)
        run_id = opaque_id("bivariate-run", f"{user_id}:{bivariate_source_id(selection)}")
        run = self._repository.bivariate_run(run_id, user_id)
        if run.status != "running":
            return
        source_run = self._repository.univariate_run(selection.source_run_id, user_id)
        quote_run_id = self._repository.quote_run_id(source_run.run_id)
        quote_rows = self._repository.quote_rows(quote_run_id)
        if not quote_rows:
            quote_rows = self._data.selected_rows(selection.member_ids, dataset="quotes")
        if not quote_rows:
            self._fail(run, user_id)
            return

        def update_progress(completed: int, total: int) -> None:
            active = self._repository.find_bivariate_run(run_id)
            if active is not None and active.status == "running":
                self._repository.save_bivariate_run(
                    replace(active, completed=min(completed, total), total=total)
                )

        try:
            computed = create_bivariate_run(
                user_id=user_id,
                selection=selection,
                quote_rows=quote_rows,
                on_progress=update_progress,
            )
        except HostedResearchError:
            self._fail(run, user_id)
            return
        self._repository.save_bivariate_run(
            replace(computed, run_id=run_id, total=computed.total, completed=computed.total)
        )
        self._repository.audit(user_id, "bivariate_statistics.complete")
        self._persistence.persist()

    def status(self, user_id: str, run_id: str) -> JsonRow:
        return research_run_row(self._repository.bivariate_run(run_id, user_id))

    def results(self, user_id: str, run_id: str, limit: int, offset: int) -> JsonRow:
        run = self._repository.bivariate_run(run_id, user_id)
        return page_rows(run.rows, limit=limit, offset=offset)

    def summary(self, user_id: str, run_id: str) -> JsonRow:
        return build_bivariate_summary(self._repository.bivariate_run(run_id, user_id).rows)

    def correlation_matrix(self, user_id: str, run_id: str, metric: str) -> JsonRow:
        run = self._repository.bivariate_run(run_id, user_id)
        return build_correlation_matrix(run.rows, metric)

    def covariance_matrix(self, user_id: str, run_id: str) -> JsonRow:
        run = self._repository.bivariate_run(run_id, user_id)
        selection = next(
            (
                item
                for item in self._repository.univariate_selections(user_id)
                if bivariate_source_id(item) == run.source_id
            ),
            None,
        )
        if selection is None:
            raise HostedApplicationError(404, "not_found")
        quote_run_id = self._repository.quote_run_id(selection.source_run_id)
        quotes = self._repository.quote_rows(quote_run_id)
        if not quotes:
            quotes = self._data.selected_rows(selection.member_ids, dataset="quotes")
        return build_covariance_matrix(quotes, selection.member_ids)

    def _fail(self, run: ResearchRun, user_id: str) -> None:
        self._repository.save_bivariate_run(replace(run, status="failed", failed=run.total))
        self._repository.audit(user_id, "bivariate_statistics.failed")
        self._persistence.persist()
