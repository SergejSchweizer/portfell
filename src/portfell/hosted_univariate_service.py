"""Univariate computation and project-scoped selection service."""

from __future__ import annotations

from dataclasses import replace

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_serializers import (
    research_run_row,
    univariate_metric_rows,
    univariate_selection_row,
)
from portfell.hosted_api_service_support import opaque_id, stable_hash
from portfell.hosted_research_ports import (
    ResearchDataPort,
    ResearchPersistencePort,
    ResearchRunRepository,
)
from portfell.hosted_research_workflow import (
    HostedResearchError,
    ResearchRun,
    create_full_univariate_selection,
    create_univariate_run,
    create_univariate_run_from_statistics,
    create_univariate_selection,
    page_rows,
)
from portfell.table_io import JsonRow


class UnivariateResearchService:
    """Own univariate computation and its resulting persisted selections."""

    def __init__(
        self,
        repository: ResearchRunRepository,
        data: ResearchDataPort,
        persistence: ResearchPersistencePort,
    ) -> None:
        self._repository = repository
        self._data = data
        self._persistence = persistence

    def start(self, user_id: str, selection_id: str, quote_run_id: str | None) -> JsonRow:
        selection = self._repository.metadata_selection(selection_id, user_id)
        source_quote_id = "shared-market" if quote_run_id is None else quote_run_id
        if quote_run_id is not None:
            quote_run = self._repository.quote_run(quote_run_id, user_id)
            if quote_run.status != "succeeded":
                raise HostedApplicationError(409, "quote_run_incomplete")
            source_quote_id = quote_run.download_run_id
        elif not self._data.has_selected_rows(selection.member_ids, dataset="quotes"):
            raise HostedApplicationError(409, "shared_market_data_incomplete")
        source_id = _source_id(selection.selection_id, source_quote_id)
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
        if quote_run_id is not None:
            self._repository.bind_quote_run(run.run_id, source_quote_id)
        self._repository.audit(user_id, "univariate_statistics.start")
        return research_run_row(run)

    def complete(self, user_id: str, selection_id: str, quote_run_id: str | None) -> None:
        """Compute a previously created run outside the request-response lifecycle."""

        run: ResearchRun | None = None
        try:
            selection = self._repository.metadata_selection(selection_id, user_id)
            source_quote_id = "shared-market" if quote_run_id is None else quote_run_id
            if quote_run_id is not None:
                source_quote_id = self._repository.quote_run(quote_run_id, user_id).download_run_id
            run_id = opaque_id(
                "univariate-run",
                f"{user_id}:{_source_id(selection.selection_id, source_quote_id)}",
            )
            run = self._repository.univariate_run(run_id, user_id)
            if run.status != "running":
                return
            quote_rows = (
                () if quote_run_id is None else self._repository.quote_rows(source_quote_id)
            )
            if quote_rows:
                computed = create_univariate_run(
                    user_id=user_id,
                    selection_id=selection.selection_id,
                    quote_run_id=source_quote_id,
                    quote_rows=quote_rows,
                    dividend_rows=self._data.selected_rows(
                        selection.member_ids, dataset="dividends"
                    ),
                )
            else:
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
                    quote_run_id=source_quote_id,
                    rows=rows,
                )
            completed = replace(computed, run_id=run_id, total=run.total, completed=run.total)
            self._repository.save_univariate_run(completed)
            full_selection = create_full_univariate_selection(user_id=user_id, run=completed)
            saved_selection = self._repository.save_univariate_selection(full_selection)
            self._repository.set_current_univariate_selection(user_id, saved_selection.selection_id)
            self._repository.audit(user_id, "univariate_statistics.compute")
            self._persistence.persist()
        except Exception:
            if run is not None:
                self._fail(run)
            raise

    def _fail(self, run: ResearchRun) -> None:
        self._repository.save_univariate_run(replace(run, status="failed", failed=run.total))
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


def _source_id(selection_id: str, quote_run_id: str) -> str:
    return stable_hash({"selection_id": selection_id, "quote_run_id": quote_run_id})
