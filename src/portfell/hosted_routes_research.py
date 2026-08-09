"""Research and analysis route registration."""

# pyright: reportUnusedFunction=false
# ruff: noqa: B008

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header

from portfell.hosted_api_contracts import (
    AnalysisCreateRequest,
    BivariateSelectionRequest,
    UnivariateRunRequest,
    UnivariateSelectionRequest,
)
from portfell.hosted_api_state import ApiUser
from portfell.hosted_research_service import ResearchService
from portfell.hosted_routes_common import JsonRow, call


def research_router(
    service: ResearchService,
    *,
    current_user: Callable[[], ApiUser],
    workspace_user: Callable[[], ApiUser],
) -> APIRouter:
    """Build research routes around the research application service."""

    router = APIRouter()

    @router.post("/univariate-statistics/runs")
    def start_univariate(
        payload: UnivariateRunRequest,
        background_tasks: BackgroundTasks,
        user: ApiUser = Depends(workspace_user),
    ) -> JsonRow:
        row = call(
            service.start_univariate,
            user.user_id,
            payload.metadata_selection_id,
            payload.quote_run_id,
        )
        if row["status"] == "running":
            background_tasks.add_task(
                service.complete_univariate,
                user.user_id,
                payload.metadata_selection_id,
                payload.quote_run_id,
            )
        return row

    @router.get("/univariate-statistics/runs/{run_id}")
    def univariate_status(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.univariate_status, user.user_id, run_id)

    @router.get("/univariate-statistics/runs/{run_id}/results")
    def univariate_results(
        run_id: str,
        user: ApiUser = Depends(current_user),
        limit: int = 50,
        offset: int = 0,
    ) -> JsonRow:
        return call(service.univariate_results, user.user_id, run_id, limit, offset)

    @router.get("/univariate-selection/metrics")
    def selection_metrics(user: ApiUser = Depends(current_user)) -> JsonRow:
        _ = user
        return call(service.selection_metrics)

    @router.post("/univariate-selection")
    def apply_selection(
        payload: UnivariateSelectionRequest, user: ApiUser = Depends(workspace_user)
    ) -> JsonRow:
        predicates = [predicate.model_dump() for predicate in payload.predicates]
        return call(service.apply_selection, user.user_id, payload.source_run_id, predicates)

    @router.get("/univariate-selection/{selection_id}/results")
    def selection_results(
        selection_id: str,
        user: ApiUser = Depends(current_user),
        limit: int = 50,
        offset: int = 0,
    ) -> JsonRow:
        return call(service.selection_results, user.user_id, selection_id, limit, offset)

    @router.post("/bivariate-statistics/plan")
    def bivariate_plan(
        payload: BivariateSelectionRequest,
        user: ApiUser = Depends(workspace_user),
    ) -> JsonRow:
        return call(
            service.bivariate_plan,
            user.user_id,
            payload.univariate_selection_id,
        )

    @router.post("/bivariate-statistics/runs")
    def start_bivariate(
        payload: BivariateSelectionRequest,
        background_tasks: BackgroundTasks,
        user: ApiUser = Depends(workspace_user),
    ) -> JsonRow:
        row = call(
            service.start_bivariate,
            user.user_id,
            payload.univariate_selection_id,
        )
        if row["status"] == "running":
            background_tasks.add_task(
                service.complete_bivariate,
                user.user_id,
                payload.univariate_selection_id,
            )
        return row

    @router.get("/bivariate-statistics/runs/{run_id}")
    def bivariate_status(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.bivariate_status, user.user_id, run_id)

    @router.get("/bivariate-statistics/runs/{run_id}/results")
    def bivariate_results(
        run_id: str,
        user: ApiUser = Depends(current_user),
        limit: int = 50,
        offset: int = 0,
    ) -> JsonRow:
        return call(service.bivariate_results, user.user_id, run_id, limit, offset)

    @router.get("/bivariate-statistics/runs/{run_id}/summary")
    def bivariate_summary(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.bivariate_summary, user.user_id, run_id)

    @router.get("/bivariate-statistics/runs/{run_id}/correlation-matrix")
    def bivariate_correlation_matrix(
        run_id: str,
        metric: Literal[
            "pearson",
            "spearman",
            "downside",
            "lower_tail_dependence",
            "tail_coexceedance_rate",
            "drawdown_overlap",
        ] = "pearson",
        user: ApiUser = Depends(current_user),
    ) -> JsonRow:
        return call(service.bivariate_correlation_matrix, user.user_id, run_id, metric)

    @router.get("/bivariate-statistics/runs/{run_id}/covariance-matrix")
    def bivariate_covariance_matrix(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.bivariate_covariance_matrix, user.user_id, run_id)

    @router.get("/bivariate-statistics/runs/{run_id}/tail-risk-scatter")
    def bivariate_tail_risk_scatter(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.bivariate_tail_risk_scatter, user.user_id, run_id)

    @router.post("/analyses")
    def create_analysis(
        payload: AnalysisCreateRequest,
        user: ApiUser = Depends(workspace_user),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JsonRow:
        return call(
            service.create_analysis,
            user.user_id,
            payload.project_id,
            payload.selection_id,
            payload.settings,
            idempotency_key,
        )

    @router.get("/analyses/{run_id}")
    def analysis_status(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.analysis_status, user.user_id, run_id)

    @router.get("/analyses/{run_id}/metrics")
    def analysis_metrics(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.analysis_metrics, user.user_id, run_id)

    @router.get("/analyses/{run_id}/returns")
    def analysis_returns(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.analysis_returns, user.user_id, run_id)

    @router.get("/analyses/{run_id}/weights")
    def analysis_weights(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.analysis_weights, user.user_id, run_id)

    @router.get("/analyses/{run_id}/report")
    def analysis_report(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.analysis_report, user.user_id, run_id)

    return router
