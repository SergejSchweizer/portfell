"""Univariate research service backed exclusively by the external market gateway."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import cast

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_serializers import research_run_row
from portfell.hosted_api_service_support import opaque_id
from portfell.hosted_market_source_research_data import (
    MarketResearchSnapshot,
    MarketSourceResearchData,
)
from portfell.hosted_research_ports import (
    ResearchDataPort,
    ResearchPersistencePort,
    ResearchRunRepository,
)
from portfell.hosted_research_workflow import (
    ResearchRun,
    create_full_univariate_selection,
    create_univariate_run,
    univariate_source_id,
)
from portfell.hosted_univariate_service import UnivariateResearchService
from portfell.market_source.errors import MarketSourceError
from portfell.market_source.projection import MarketProjectionError
from portfell.table_io import JsonRow


class MarketSourceUnivariateResearchService(UnivariateResearchService):
    """Cut Univariate reads over to one coherent external PostgreSQL snapshot."""

    def __init__(
        self,
        repository: ResearchRunRepository,
        data: MarketSourceResearchData,
        persistence: ResearchPersistencePort,
        workflow_projector: Callable[[str, str], object] | None = None,
    ) -> None:
        # The base class still serves explicit local/test compatibility until the deletion wave.
        # Its data port is never used by the two source-cutover methods overridden below.
        super().__init__(repository, cast(ResearchDataPort, data), persistence, workflow_projector)
        self._market_data = data

    def start(self, user_id: str, selection_id: str) -> JsonRow:
        selection = self._repository.metadata_selection(selection_id, user_id)
        market = self._read_market(selection.member_ids)
        source_id = univariate_source_id(selection.selection_id, market.snapshot_id)
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
        """Compute from a freshly materialized coherent snapshot outside the DB transaction."""

        run: ResearchRun | None = None
        try:
            selection = self._repository.metadata_selection(selection_id, user_id)
            market = self._read_market(selection.member_ids)
            source_id = univariate_source_id(selection.selection_id, market.snapshot_id)
            run_id = opaque_id("univariate-run", f"{user_id}:{source_id}")
            run = self._repository.univariate_run(run_id, user_id)
            if run.status != "running":
                return
            computed = create_univariate_run(
                user_id=user_id,
                selection_id=selection.selection_id,
                quote_run_id=market.snapshot_id,
                quote_rows=market.quotes,
                dividend_rows=market.dividends,
                on_progress=lambda completed: self._update_progress(user_id, run_id, completed),
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

    def _read_market(self, member_ids: tuple[str, ...]) -> MarketResearchSnapshot:
        try:
            return self._market_data.read(member_ids)
        except (MarketSourceError, MarketProjectionError) as error:
            raise HostedApplicationError(409, error.code) from error


__all__ = ["MarketSourceUnivariateResearchService"]
