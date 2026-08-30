"""Univariate computation and project-scoped selection service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_serializers import (
    research_run_row,
    univariate_metric_rows,
    univariate_selection_row,
)
from portfell.hosted_api_service_support import opaque_id
from portfell.hosted_research_ports import (
    ResearchDataPort,
    ResearchPersistencePort,
    ResearchRunRepository,
)
from portfell.hosted_research_workflow import (
    HostedResearchError,
    ResearchRun,
    create_full_univariate_selection,
    create_univariate_run_from_statistics,
    create_univariate_selection,
    page_rows,
    univariate_source_id,
)
from portfell.table_io import JsonRow


class UnivariateResearchService:
    """Own univariate computation and its resulting persisted selections."""

    def __init__(
        self,
        repository: ResearchRunRepository,
        data: ResearchDataPort,
        persistence: ResearchPersistencePort,
        workflow_projector: Callable[[str, str], object] | None = None,
    ) -> None:
        self._repository = repository
        self._data = data
        self._persistence = persistence
        self._workflow_projector = workflow_projector

    def start(self, user_id: str, selection_id: str) -> JsonRow:
        selection = self._repository.metadata_selection(selection_id, user_id)
        if not self._data.has_selected_rows(selection.member_ids, dataset="quotes"):
            raise HostedApplicationError(409, "shared_market_data_incomplete")
        source_id = _source_id(selection.selection_id)
        run_id = opaque_id("univariate-run", f"{user_id}:{source_id}")
        existing = self._repository.find_univariate_run(run_id, user_id)
        if existing is not None:
            if existing.status != "failed":
                return research_run_row(existing)
            self._repository.delete_univariate_run(run_id)
        run = ResearchRun(
            run_id=run_id,
            user_id=user_id,
            source_id=source_id,
            status="running",
            rows=(),
            total=len(selection.member_ids),
            completed=0,
        )
        self._repository.save_univariate_run(run)
        self._repository.bind_project_run(
            user_id=user_id, project_id=selection.project_id, run_id=run.run_id
        )
        self._project(user_id, selection.project_id)
        self._repository.audit(user_id, "univariate_statistics.start")
        return research_run_row(run)

    def complete(self, user_id: str, selection_id: str) -> None:
        """Compute a previously created run outside the request-response lifecycle."""

        run: ResearchRun | None = None
        try:
            selection = self._repository.metadata_selection(selection_id, user_id)
            run_id = opaque_id(
                "univariate-run",
                f"{user_id}:{_source_id(selection.selection_id)}",
            )
            run = self._repository.univariate_run(run_id, user_id)
            if run.status != "running":
                return
            rows = self._data.build_univariate_rows(
                selection.member_ids,
                on_progress=lambda completed: self._update_progress(user_id, run_id, completed),
            )
            if not rows:
                self._fail(run)
                return
            computed = create_univariate_run_from_statistics(
                user_id=user_id,
                selection_id=selection.selection_id,
                quote_run_id="market-source",
                rows=rows,
            )
            completed = replace(computed, run_id=run_id, total=run.total, completed=run.total)
            self._repository.save_univariate_run(completed)
            full_selection = create_full_univariate_selection(user_id=user_id, run=completed)
            saved_selection = self._repository.save_univariate_selection(full_selection)
            self._repository.set_current_univariate_selection(user_id, saved_selection.selection_id)
            self._project(user_id, selection.project_id)
            self._repository.audit(user_id, "univariate_statistics.compute")
            self._persistence.persist()
        except Exception:
            if run is not None:
                self._fail(run)
            raise

    def _fail(self, run: ResearchRun) -> None:
        self._repository.save_univariate_run(replace(run, status="failed", failed=run.total))
        project_id = self._repository.project_id_for_run(user_id=run.user_id, run_id=run.run_id)
        if project_id is not None:
            self._project(run.user_id, project_id)
        self._repository.audit(run.user_id, "univariate_statistics.failed")
        self._persistence.persist()

    def status(self, user_id: str, run_id: str) -> JsonRow:
        return research_run_row(self._repository.univariate_run(run_id, user_id))

    def results(self, user_id: str, run_id: str, limit: int, offset: int) -> JsonRow:
        run = self._repository.univariate_run(run_id, user_id)
        return page_rows(run.rows, limit=limit, offset=offset)

    def selection_metrics(self) -> JsonRow:
        return {"items": univariate_metric_rows()}

    def apply_selection(
        self, user_id: str, source_run_id: str, predicates: list[JsonRow]
    ) -> JsonRow:
        run = self._repository.univariate_run(source_run_id, user_id)
        try:
            selection = create_univariate_selection(
                user_id=user_id, run=run, predicate_rows=predicates
            )
        except HostedResearchError as error:
            raise HostedApplicationError(422, str(error)) from error
        saved = self._repository.save_univariate_selection(selection)
        self._repository.set_current_univariate_selection(user_id, saved.selection_id)
        self._persistence.persist()
        return univariate_selection_row(saved)

    def selection_results(
        self, user_id: str, selection_id: str, limit: int, offset: int
    ) -> JsonRow:
        selection = self._repository.univariate_selection(selection_id, user_id)
        return page_rows(selection.rows, limit=limit, offset=offset)

    def _update_progress(self, user_id: str, run_id: str, completed: int) -> None:
        run = self._repository.find_univariate_run(run_id, user_id)
        if run is not None and run.status == "running":
            self._repository.save_univariate_run(replace(run, completed=min(completed, run.total)))
            project_id = self._repository.project_id_for_run(user_id=user_id, run_id=run_id)
            if project_id is not None:
                self._project(user_id, project_id)

    def _project(self, user_id: str, project_id: str) -> None:
        if self._workflow_projector is not None:
            self._workflow_projector(user_id, project_id)


def _source_id(selection_id: str) -> str:
    return univariate_source_id(selection_id, "market-source")
