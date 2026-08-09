"""Stable facade over concern-specific hosted research services."""

from __future__ import annotations

from portfell.hosted_analysis_service import HostedAnalysisService
from portfell.hosted_api_state import AnalysisRecord
from portfell.hosted_bivariate_service import BivariateResearchService
from portfell.hosted_multivariate_service import MultivariateResearchService
from portfell.hosted_univariate_service import UnivariateResearchService
from portfell.table_io import JsonRow


class ResearchService:
    """Preserve the route-facing API while delegating each research responsibility."""

    def __init__(
        self,
        univariate: UnivariateResearchService,
        bivariate: BivariateResearchService,
        multivariate: MultivariateResearchService,
        analysis: HostedAnalysisService,
    ) -> None:
        self._univariate = univariate
        self._bivariate = bivariate
        self._multivariate = multivariate
        self._analysis = analysis

    def start_univariate(self, user_id: str, selection_id: str, quote_run_id: str) -> JsonRow:
        return self._univariate.start(user_id, selection_id, quote_run_id)

    def complete_univariate(self, user_id: str, selection_id: str, quote_run_id: str) -> None:
        self._univariate.complete(user_id, selection_id, quote_run_id)

    def univariate_status(self, user_id: str, run_id: str) -> JsonRow:
        return self._univariate.status(user_id, run_id)

    def univariate_results(self, user_id: str, run_id: str, limit: int, offset: int) -> JsonRow:
        return self._univariate.results(user_id, run_id, limit, offset)

    def selection_metrics(self) -> JsonRow:
        return self._univariate.selection_metrics()

    def apply_selection(
        self, user_id: str, source_run_id: str, predicates: list[JsonRow]
    ) -> JsonRow:
        return self._univariate.apply_selection(user_id, source_run_id, predicates)

    def selection_results(
        self, user_id: str, selection_id: str, limit: int, offset: int
    ) -> JsonRow:
        return self._univariate.selection_results(user_id, selection_id, limit, offset)

    def bivariate_plan(self, user_id: str, selection_id: str) -> JsonRow:
        return self._bivariate.plan(user_id, selection_id)

    def start_bivariate(self, user_id: str, selection_id: str) -> JsonRow:
        return self._bivariate.start(user_id, selection_id)

    def complete_bivariate(self, user_id: str, selection_id: str) -> None:
        self._bivariate.complete(user_id, selection_id)

    def bivariate_status(self, user_id: str, run_id: str) -> JsonRow:
        return self._bivariate.status(user_id, run_id)

    def bivariate_results(self, user_id: str, run_id: str, limit: int, offset: int) -> JsonRow:
        return self._bivariate.results(user_id, run_id, limit, offset)

    def bivariate_summary(self, user_id: str, run_id: str) -> JsonRow:
        return self._bivariate.summary(user_id, run_id)

    def bivariate_correlation_matrix(self, user_id: str, run_id: str, metric: str) -> JsonRow:
        return self._bivariate.correlation_matrix(user_id, run_id, metric)

    def bivariate_covariance_matrix(self, user_id: str, run_id: str) -> JsonRow:
        return self._bivariate.covariance_matrix(user_id, run_id)

    def bivariate_tail_risk_scatter(self, user_id: str, run_id: str) -> JsonRow:
        return self._bivariate.tail_risk_scatter(user_id, run_id)

    def start_multivariate(
        self, user_id: str, project_id: str, bivariate_run_id: str, settings: JsonRow
    ) -> JsonRow:
        return self._multivariate.start(user_id, project_id, bivariate_run_id, settings)

    def plan_multivariate(
        self, user_id: str, project_id: str, bivariate_run_id: str, settings: JsonRow
    ) -> JsonRow:
        return self._multivariate.plan(user_id, project_id, bivariate_run_id, settings)

    def complete_multivariate(self, user_id: str, run_id: str) -> None:
        self._multivariate.complete(user_id, run_id)

    def multivariate_status(self, user_id: str, run_id: str) -> JsonRow:
        return self._multivariate.status(user_id, run_id)

    def multivariate_summary(self, user_id: str, run_id: str) -> JsonRow:
        return self._multivariate.summary(user_id, run_id)

    def multivariate_structure(self, user_id: str, run_id: str) -> JsonRow:
        return self._multivariate.structure(user_id, run_id)

    def multivariate_candidates(self, user_id: str, run_id: str) -> JsonRow:
        return self._multivariate.candidates(user_id, run_id)

    def multivariate_candidate_detail(
        self, user_id: str, run_id: str, candidate_id: str
    ) -> JsonRow:
        return self._multivariate.candidate_detail(user_id, run_id, candidate_id)

    def multivariate_risk_contributions(
        self, user_id: str, run_id: str, candidate_id: str | None
    ) -> JsonRow:
        return self._multivariate.risk_contributions(user_id, run_id, candidate_id)

    def multivariate_income_evidence(self, user_id: str, run_id: str) -> JsonRow:
        return self._multivariate.income_evidence(user_id, run_id)

    def multivariate_components(
        self, user_id: str, run_id: str, limit: int, offset: int
    ) -> JsonRow:
        return self._multivariate.components(user_id, run_id, limit, offset)

    def multivariate_validation(self, user_id: str, run_id: str) -> JsonRow:
        return self._multivariate.validation(user_id, run_id)

    def multivariate_artifacts(self, user_id: str, run_id: str) -> JsonRow:
        return self._multivariate.artifacts(user_id, run_id)

    def update_multivariate_settings(
        self, user_id: str, run_id: str, selected_candidate_ids: tuple[str, ...]
    ) -> JsonRow:
        return self._multivariate.update_settings(user_id, run_id, selected_candidate_ids)

    def create_analysis(
        self,
        user_id: str,
        project_id: str,
        selection_id: str,
        settings: JsonRow,
        idempotency_key: str | None,
    ) -> JsonRow:
        return self._analysis.create(user_id, project_id, selection_id, settings, idempotency_key)

    def analysis(self, user_id: str, run_id: str) -> AnalysisRecord:
        return self._analysis.analysis(user_id, run_id)

    def analysis_status(self, user_id: str, run_id: str) -> JsonRow:
        return self._analysis.status(user_id, run_id)

    def analysis_metrics(self, user_id: str, run_id: str) -> JsonRow:
        return self._analysis.metrics(user_id, run_id)

    def analysis_returns(self, user_id: str, run_id: str) -> JsonRow:
        return self._analysis.returns(user_id, run_id)

    def analysis_weights(self, user_id: str, run_id: str) -> JsonRow:
        return self._analysis.weights(user_id, run_id)

    def analysis_report(self, user_id: str, run_id: str) -> JsonRow:
        return self._analysis.report(user_id, run_id)


__all__ = ["ResearchService"]
