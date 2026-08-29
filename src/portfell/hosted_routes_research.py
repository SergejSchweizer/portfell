"""Research and analysis route registration."""

# pyright: reportUnusedFunction=false
# ruff: noqa: B008

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Literal, cast

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response
from fastapi.responses import JSONResponse

from portfell.hosted_api_contracts import (
    AnalysisCreateRequest,
    BivariateSelectionRequest,
    MultivariateRunRequest,
    MultivariateSettingsRequest,
    UnivariateRunRequest,
    UnivariateSelectionRequest,
)
from portfell.hosted_api_state import ApiUser
from portfell.hosted_credential_project_service import CredentialProjectService
from portfell.hosted_page_view_contracts import (
    analytical_page_view,
    bounded_detail_section,
    decode_section_cursor,
    encode_section_cursor,
)
from portfell.hosted_postgres_request_scope import RequestScopedPostgresConnection
from portfell.hosted_research_service import ResearchService
from portfell.hosted_routes_common import JsonRow, call


def research_router(
    service: ResearchService,
    projects: CredentialProjectService,
    *,
    current_user: Callable[[], ApiUser],
    workspace_user: Callable[[], ApiUser],
    request_scope: RequestScopedPostgresConnection | None = None,
) -> APIRouter:
    """Build research routes around the research application service."""

    router = APIRouter()

    def page_view_response(
        *, module: str, project_id: str, user: ApiUser, if_none_match: str | None
    ) -> Response:
        workflow = call(projects.workflow, user.user_id, project_id)
        row, etag = analytical_page_view(module=module, project_id=project_id, workflow=workflow)
        headers = {"ETag": f'"{etag}"', "Cache-Control": "private, max-age=0, must-revalidate"}
        if if_none_match == headers["ETag"]:
            return Response(status_code=304, headers=headers)
        return JSONResponse(content=row, headers=headers)

    def lazy_tabular_section(
        *,
        module: str,
        section: str,
        project_id: str,
        user: ApiUser,
        cursor: str | None,
        metric: str,
        candidate_id: str | None,
    ) -> JsonRow:
        workflow = call(projects.workflow, user.user_id, project_id)
        page_view, _ = analytical_page_view(module=module, project_id=project_id, workflow=workflow)
        sections = cast(JsonRow, page_view["sections"])
        section_row = sections.get(section)
        if not isinstance(section_row, dict):
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        typed_section = cast(JsonRow, section_row)
        if typed_section.get("available") is not True:
            raise HTTPException(status_code=409, detail={"code": "section_not_available"})
        revision = typed_section.get("revision")
        run_id = page_view.get("run_id")
        if not isinstance(revision, str) or not isinstance(run_id, str):
            raise HTTPException(status_code=409, detail={"code": "section_not_available"})
        try:
            offset = (
                0 if cursor is None else decode_section_cursor(cursor=cursor, revision=revision)
            )
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=409, detail={"code": code}) from error
        if module == "univariate_statistics" and section == "results":
            result = call(service.univariate_results, user.user_id, run_id, 200, offset)
        elif module == "univariate_statistics" and section == "selection_results":
            stages = cast(JsonRow, workflow["stages"])
            stage = cast(JsonRow, stages[module])
            selection_id = stage.get("univariate_selection_id")
            if not isinstance(selection_id, str):
                raise HTTPException(status_code=409, detail={"code": "section_not_available"})
            result = call(service.selection_results, user.user_id, selection_id, 200, offset)
        elif module == "bivariate_statistics" and section == "results":
            result = call(service.bivariate_results, user.user_id, run_id, 200, offset)
        elif module == "multivariate_statistics" and section == "components":
            result = call(service.multivariate_components, user.user_id, run_id, 200, offset)
        elif module == "bivariate_statistics" and section == "summary":
            return detail_response(
                revision, section, call(service.bivariate_summary, user.user_id, run_id)
            )
        elif module == "bivariate_statistics" and section == "covariance_matrix":
            return detail_response(
                revision, section, call(service.bivariate_covariance_matrix, user.user_id, run_id)
            )
        elif module == "bivariate_statistics" and section == "correlation_matrix":
            return detail_response(
                revision,
                section,
                call(service.bivariate_correlation_matrix, user.user_id, run_id, metric),
            )
        elif module == "bivariate_statistics" and section == "tail_risk_scatter":
            return detail_response(
                revision, section, call(service.bivariate_tail_risk_scatter, user.user_id, run_id)
            )
        elif module == "multivariate_statistics" and section == "summary":
            return detail_response(
                revision, section, call(service.multivariate_summary, user.user_id, run_id)
            )
        elif module == "multivariate_statistics" and section == "structure":
            return detail_response(
                revision, section, call(service.multivariate_structure, user.user_id, run_id)
            )
        elif module == "multivariate_statistics" and section == "candidates":
            return detail_response(
                revision, section, call(service.multivariate_candidates, user.user_id, run_id)
            )
        elif module == "multivariate_statistics" and section == "candidate_detail":
            if candidate_id is None:
                raise HTTPException(status_code=422, detail={"code": "candidate_id_required"})
            return detail_response(
                revision,
                section,
                call(service.multivariate_candidate_detail, user.user_id, run_id, candidate_id),
            )
        elif module == "multivariate_statistics" and section == "risk_contributions":
            return detail_response(
                revision,
                section,
                call(service.multivariate_risk_contributions, user.user_id, run_id, candidate_id),
            )
        elif module == "multivariate_statistics" and section == "income_evidence":
            return detail_response(
                revision, section, call(service.multivariate_income_evidence, user.user_id, run_id)
            )
        elif module == "multivariate_statistics" and section == "validation":
            return detail_response(
                revision, section, call(service.multivariate_validation, user.user_id, run_id)
            )
        elif module == "multivariate_statistics" and section == "artifacts":
            return detail_response(
                revision, section, call(service.multivariate_artifacts, user.user_id, run_id)
            )
        elif module == "multivariate_statistics" and section == "performance":
            return detail_response(
                revision, section, call(service.multivariate_performance, user.user_id, run_id)
            )
        else:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        raw_items = result.get("items")
        total = result.get("total")
        if not isinstance(raw_items, list) or not isinstance(total, int):
            raise HTTPException(status_code=500, detail={"code": "section_response_invalid"})
        items = cast(list[JsonRow], raw_items)
        row: JsonRow = {"revision": revision, "items": items, "total": total, "limit": 200}
        next_offset = offset + len(items)
        row["next_cursor"] = (
            None
            if next_offset >= total
            else encode_section_cursor(revision=revision, offset=next_offset)
        )
        if len(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()) > 2 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail={"code": "section_too_large", "section": section, "revision": revision},
            )
        return row

    def detail_response(revision: str, section: str, payload: JsonRow) -> JsonRow:
        try:
            return bounded_detail_section(revision=revision, payload=payload)
        except ValueError as error:
            raise HTTPException(
                status_code=413,
                detail={"code": str(error), "section": section, "revision": revision},
            ) from error

    @router.get("/projects/{project_id}/views/{module}/sections/{section}")
    def analytical_tabular_section(
        project_id: str,
        module: Literal["univariate_statistics", "bivariate_statistics", "multivariate_statistics"],
        section: str,
        cursor: str | None = None,
        metric: Literal[
            "pearson",
            "spearman",
            "downside",
            "lower_tail_dependence",
            "tail_coexceedance_rate",
            "drawdown_overlap",
            "rolling_stability",
        ] = "pearson",
        candidate_id: str | None = None,
        user: ApiUser = Depends(current_user),
    ) -> JsonRow:
        return lazy_tabular_section(
            module=module,
            section=section,
            project_id=project_id,
            user=user,
            cursor=cursor,
            metric=metric,
            candidate_id=candidate_id,
        )

    @router.get("/projects/{project_id}/views/univariate-statistics")
    def univariate_page_view(
        project_id: str,
        user: ApiUser = Depends(current_user),
        if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    ) -> Response:
        return page_view_response(
            module="univariate_statistics",
            project_id=project_id,
            user=user,
            if_none_match=if_none_match,
        )

    @router.get("/projects/{project_id}/views/bivariate-statistics")
    def bivariate_page_view(
        project_id: str,
        user: ApiUser = Depends(current_user),
        if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    ) -> Response:
        return page_view_response(
            module="bivariate_statistics",
            project_id=project_id,
            user=user,
            if_none_match=if_none_match,
        )

    @router.get("/projects/{project_id}/views/multivariate-statistics")
    def multivariate_page_view(
        project_id: str,
        user: ApiUser = Depends(current_user),
        if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    ) -> Response:
        return page_view_response(
            module="multivariate_statistics",
            project_id=project_id,
            user=user,
            if_none_match=if_none_match,
        )

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
            if request_scope is None:
                background_tasks.add_task(
                    service.complete_univariate,
                    user.user_id,
                    payload.metadata_selection_id,
                    payload.quote_run_id,
                )
            else:
                request_scope.spawn_after_commit(
                    user_id=user.user_id,
                    operation=lambda: service.complete_univariate(
                        user.user_id, payload.metadata_selection_id, payload.quote_run_id
                    ),
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
            if request_scope is None:
                background_tasks.add_task(
                    service.complete_bivariate,
                    user.user_id,
                    payload.univariate_selection_id,
                )
            else:
                request_scope.spawn_after_commit(
                    user_id=user.user_id,
                    operation=lambda: service.complete_bivariate(
                        user.user_id, payload.univariate_selection_id
                    ),
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
            "rolling_stability",
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

    @router.post("/multivariate-statistics/plan")
    def plan_multivariate(
        payload: MultivariateRunRequest, user: ApiUser = Depends(workspace_user)
    ) -> JsonRow:
        return call(
            service.plan_multivariate,
            user.user_id,
            str(payload.project_id),
            payload.bivariate_run_id,
            payload.settings.model_dump(),
        )

    @router.post("/multivariate-statistics/runs")
    def start_multivariate(
        payload: MultivariateRunRequest,
        background_tasks: BackgroundTasks,
        user: ApiUser = Depends(workspace_user),
    ) -> JsonRow:
        row = call(
            service.start_multivariate,
            user.user_id,
            str(payload.project_id),
            payload.bivariate_run_id,
            payload.settings.model_dump(),
        )
        if row["status"] == "running":
            if request_scope is None:
                background_tasks.add_task(
                    service.complete_multivariate, user.user_id, row["run_id"]
                )
            else:
                request_scope.spawn_after_commit(
                    user_id=user.user_id,
                    operation=lambda: service.complete_multivariate(user.user_id, row["run_id"]),
                )
        return row

    @router.get("/multivariate-statistics/runs/{run_id}")
    def multivariate_status(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.multivariate_status, user.user_id, run_id)

    @router.get("/multivariate-statistics/runs/{run_id}/summary")
    def multivariate_summary(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.multivariate_summary, user.user_id, run_id)

    @router.get("/multivariate-statistics/runs/{run_id}/structure")
    def multivariate_structure(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.multivariate_structure, user.user_id, run_id)

    @router.get("/multivariate-statistics/runs/{run_id}/candidates")
    def multivariate_candidates(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.multivariate_candidates, user.user_id, run_id)

    @router.get("/multivariate-statistics/runs/{run_id}/candidates/{candidate_id}")
    def multivariate_candidate_detail(
        run_id: str, candidate_id: str, user: ApiUser = Depends(current_user)
    ) -> JsonRow:
        return call(service.multivariate_candidate_detail, user.user_id, run_id, candidate_id)

    @router.get("/multivariate-statistics/runs/{run_id}/risk-contributions")
    def multivariate_risk_contributions(
        run_id: str,
        candidate_id: str | None = None,
        user: ApiUser = Depends(current_user),
    ) -> JsonRow:
        return call(service.multivariate_risk_contributions, user.user_id, run_id, candidate_id)

    @router.get("/multivariate-statistics/runs/{run_id}/income-evidence")
    def multivariate_income_evidence(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.multivariate_income_evidence, user.user_id, run_id)

    @router.get("/multivariate-statistics/runs/{run_id}/components")
    def multivariate_components(
        run_id: str,
        limit: int = 25,
        offset: int = 0,
        user: ApiUser = Depends(current_user),
    ) -> JsonRow:
        return call(service.multivariate_components, user.user_id, run_id, limit, offset)

    @router.get("/multivariate-statistics/runs/{run_id}/validation")
    def multivariate_validation(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.multivariate_validation, user.user_id, run_id)

    @router.get("/multivariate-statistics/runs/{run_id}/artifacts")
    def multivariate_artifacts(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.multivariate_artifacts, user.user_id, run_id)

    @router.get("/multivariate-statistics/runs/{run_id}/performance")
    def multivariate_performance(run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.multivariate_performance, user.user_id, run_id)

    @router.patch("/multivariate-statistics/runs/{run_id}/settings")
    def update_multivariate_settings(
        run_id: str,
        payload: MultivariateSettingsRequest,
        user: ApiUser = Depends(workspace_user),
    ) -> JsonRow:
        return call(
            service.update_multivariate_settings,
            user.user_id,
            run_id,
            tuple(payload.selected_candidate_ids),
        )

    @router.post("/analyses")
    def create_analysis(
        payload: AnalysisCreateRequest,
        user: ApiUser = Depends(workspace_user),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JsonRow:
        return call(
            service.create_analysis,
            user.user_id,
            str(payload.project_id),
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
