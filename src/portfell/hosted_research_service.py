"""Research and analysis application service."""

from __future__ import annotations

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_serializers import (
    analysis_row,
    filter_selection_row,
    research_run_row,
    univariate_metric_rows,
)
from portfell.hosted_api_service_support import (
    audit,
    idempotent_response,
    opaque_id,
    remember_idempotency,
    require_user_row,
    stable_hash,
)
from portfell.hosted_api_state import AnalysisRecord, HostedApiState
from portfell.hosted_research_workflow import (
    HostedResearchError,
    create_bivariate_run,
    create_filter_selection,
    create_univariate_run,
    page_rows,
    pair_plan,
)
from portfell.table_io import JsonRow


class ResearchService:
    """Own univariate, filter, bivariate, and analysis transitions."""

    def __init__(self, state: HostedApiState) -> None:
        self.state = state

    def start_univariate(self, user_id: str, selection_id: str, quote_run_id: str) -> JsonRow:
        selection = require_user_row(self.state.selections_by_id, selection_id, user_id)
        quote_run = require_user_row(self.state.downloads_by_id, quote_run_id, user_id)
        if quote_run.status != "succeeded":
            raise HostedApplicationError(409, "quote_run_incomplete")
        quote_rows = self.state.quote_rows_by_run_id.get(quote_run.download_run_id)
        if quote_rows is None:
            raise HostedApplicationError(409, "scoped_quote_rows_unavailable")
        run = create_univariate_run(
            user_id=user_id,
            selection_id=selection.selection_id,
            quote_run_id=quote_run.download_run_id,
            quote_rows=quote_rows,
        )
        self.state.univariate_runs_by_id.setdefault(run.run_id, run)
        self.state.quote_run_by_univariate_run_id.setdefault(run.run_id, quote_run.download_run_id)
        return research_run_row(self.state.univariate_runs_by_id[run.run_id])

    def univariate_status(self, user_id: str, run_id: str) -> JsonRow:
        return research_run_row(require_user_row(self.state.univariate_runs_by_id, run_id, user_id))

    def univariate_results(self, user_id: str, run_id: str, limit: int, offset: int) -> JsonRow:
        run = require_user_row(self.state.univariate_runs_by_id, run_id, user_id)
        return page_rows(run.rows, limit=limit, offset=offset)

    def filter_metrics(self) -> JsonRow:
        return {"items": univariate_metric_rows()}

    def apply_filter(self, user_id: str, source_run_id: str, predicates: list[JsonRow]) -> JsonRow:
        run = require_user_row(self.state.univariate_runs_by_id, source_run_id, user_id)
        try:
            selection = create_filter_selection(user_id=user_id, run=run, predicate_rows=predicates)
        except HostedResearchError as error:
            raise HostedApplicationError(422, str(error)) from error
        self.state.filter_selections_by_id.setdefault(selection.selection_id, selection)
        self.state.current_filter_selection_by_user[user_id] = selection.selection_id
        return filter_selection_row(self.state.filter_selections_by_id[selection.selection_id])

    def filter_results(self, user_id: str, selection_id: str, limit: int, offset: int) -> JsonRow:
        selection = require_user_row(self.state.filter_selections_by_id, selection_id, user_id)
        return page_rows(selection.rows, limit=limit, offset=offset)

    def bivariate_plan(self, user_id: str, selection_id: str) -> JsonRow:
        selection = require_user_row(self.state.filter_selections_by_id, selection_id, user_id)
        return pair_plan(selection)

    def start_bivariate(self, user_id: str, selection_id: str) -> JsonRow:
        selection = require_user_row(self.state.filter_selections_by_id, selection_id, user_id)
        source_run = require_user_row(
            self.state.univariate_runs_by_id, selection.source_run_id, user_id
        )
        quote_run_id = self.state.quote_run_by_univariate_run_id.get(source_run.run_id, "")
        quote_rows = self.state.quote_rows_by_run_id.get(quote_run_id)
        if quote_rows is None:
            raise HostedApplicationError(409, "scoped_quote_rows_unavailable")
        try:
            run = create_bivariate_run(user_id=user_id, selection=selection, quote_rows=quote_rows)
        except HostedResearchError as error:
            raise HostedApplicationError(422, str(error)) from error
        self.state.bivariate_runs_by_id.setdefault(run.run_id, run)
        return research_run_row(self.state.bivariate_runs_by_id[run.run_id])

    def bivariate_status(self, user_id: str, run_id: str) -> JsonRow:
        return research_run_row(require_user_row(self.state.bivariate_runs_by_id, run_id, user_id))

    def bivariate_results(self, user_id: str, run_id: str, limit: int, offset: int) -> JsonRow:
        run = require_user_row(self.state.bivariate_runs_by_id, run_id, user_id)
        return page_rows(run.rows, limit=limit, offset=offset)

    def create_analysis(
        self,
        user_id: str,
        project_id: str,
        selection_id: str,
        settings: JsonRow,
        idempotency_key: str | None,
    ) -> JsonRow:
        selection = require_user_row(self.state.selections_by_id, selection_id, user_id)
        require_user_row(self.state.projects_by_id, project_id, user_id)
        logical_hash = stable_hash(
            {
                "selection_id": selection.selection_id,
                "member_ids": list(selection.member_ids),
                "settings": settings,
            }
        )
        cached = idempotent_response(
            self.state,
            user_id=user_id,
            operation="analysis",
            idempotency_key=idempotency_key,
        )
        if cached is not None:
            return {**analysis_row(self.state.analyses_by_id[cached]), "cache_hit": True}
        run_id = opaque_id("analysis", f"{user_id}:{logical_hash}")
        count = len(selection.member_ids)
        analysis = AnalysisRecord(
            run_id=run_id,
            user_id=user_id,
            project_id=project_id,
            selection_id=selection.selection_id,
            logical_hash=logical_hash,
            status="succeeded",
            metrics=({"name": "selection_size", "value": count},),
            returns=tuple(
                {"member_id": member_id, "return": 0.0} for member_id in selection.member_ids
            ),
            weights=tuple(
                {"member_id": member_id, "weight": 1 / count} for member_id in selection.member_ids
            ),
            report={"summary": "deterministic hosted analysis placeholder"},
        )
        self.state.analyses_by_id[run_id] = analysis
        remember_idempotency(self.state, user_id, "analysis", idempotency_key, run_id)
        audit(self.state, user_id, "analysis.create")
        return {**analysis_row(analysis), "cache_hit": False}

    def analysis(self, user_id: str, run_id: str) -> AnalysisRecord:
        return require_user_row(self.state.analyses_by_id, run_id, user_id)

    def analysis_status(self, user_id: str, run_id: str) -> JsonRow:
        return analysis_row(self.analysis(user_id, run_id))

    def analysis_metrics(self, user_id: str, run_id: str) -> JsonRow:
        return {"items": list(self.analysis(user_id, run_id).metrics)}

    def analysis_returns(self, user_id: str, run_id: str) -> JsonRow:
        return {"items": list(self.analysis(user_id, run_id).returns)}

    def analysis_weights(self, user_id: str, run_id: str) -> JsonRow:
        return {"items": list(self.analysis(user_id, run_id).weights)}

    def analysis_report(self, user_id: str, run_id: str) -> JsonRow:
        return self.analysis(user_id, run_id).report
