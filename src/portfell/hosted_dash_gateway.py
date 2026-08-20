"""Hosted adapter implementing the presentation-only Dash gateway contract."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from contextlib import contextmanager
from typing import Iterator, cast

from portfell.dash_ui.core.gateway import DashResearchGateway, Presentation
from portfell.dash_ui.core.routes import WorkflowId
from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_state import CurrentUserProvider
from portfell.hosted_credential_project_service import CredentialProjectService
from portfell.hosted_metadata_project_service import MetadataProjectService
from portfell.hosted_page_view_contracts import analytical_page_view, metadata_builder_page_view
from portfell.hosted_postgres_request_scope import RequestScopedPostgresConnection
from portfell.hosted_research_service import ResearchService


class HostedDashGateway(DashResearchGateway):
    """Reuse hosted services without exposing database/provider authority to Dash modules."""

    def __init__(
        self,
        *,
        projects: CredentialProjectService,
        metadata: MetadataProjectService,
        research: ResearchService,
        request_scope: RequestScopedPostgresConnection,
        current_user_provider: CurrentUserProvider,
    ) -> None:
        self._projects = projects
        self._metadata = metadata
        self._research = research
        self._request_scope = request_scope
        self._current_user_provider = current_user_provider

    @contextmanager
    def _scope(self) -> Iterator[str]:
        user_id = self._current_user_provider.current_user().user_id
        if self._request_scope.authenticated_user_id == user_id:
            yield user_id
            return
        with self._request_scope.request(user_id):
            yield user_id

    @staticmethod
    def slug(name: str) -> str:
        normalized = unicodedata.normalize("NFKD", name)
        ascii_name = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return re.sub(r"[^a-z0-9]+", "-", ascii_name.casefold()).strip("-") or "project"

    def _project_id(self, *, user_id: str, project_slug: str) -> str:
        projects = self._projects.project_context(user_id).get("projects")
        if not isinstance(projects, list):
            raise KeyError(project_slug)
        matches: list[str] = []
        for raw_project in cast(list[object], projects):
            if not isinstance(raw_project, dict):
                continue
            project = cast(dict[str, object], raw_project)
            name, project_id = project.get("name"), project.get("project_id")
            if isinstance(name, str) and isinstance(project_id, str) and self.slug(name) == project_slug:
                matches.append(project_id)
        if len(matches) != 1:
            raise KeyError(project_slug)
        return matches[0]

    def _workflow(self, *, user_id: str, project_slug: str) -> tuple[str, dict[str, object]]:
        project_id = self._project_id(user_id=user_id, project_slug=project_slug)
        return project_id, self._projects.workflow(user_id, project_id)

    def project_context(self, *, project_slug: str) -> Presentation:
        with self._scope() as user_id:
            project_id = self._project_id(user_id=user_id, project_slug=project_slug)
            context = dict(self._projects.project_context(user_id))
            context["resolved_project_id"] = project_id
            return context

    def page_view(self, *, project_slug: str, workflow: WorkflowId) -> Presentation:
        with self._scope() as user_id:
            project_id, workflow_row = self._workflow(user_id=user_id, project_slug=project_slug)
            if workflow is WorkflowId.METADATA_BUILDER:
                project, selection = self._projects.project_metadata_builder(user_id, project_id)
                criteria = self._metadata.project_criteria_row(project, selection)
                try:
                    initial_fill = self._metadata.initial_fill_status(user_id, project_id)
                except HostedApplicationError as error:
                    if error.status_code != 404 or error.code != "initial_fill_not_found":
                        raise
                    initial_fill = None
                row, _ = metadata_builder_page_view(
                    project_id=project_id,
                    criteria=criteria,
                    initial_fill=initial_fill,
                    workflow=workflow_row,
                )
                result = dict(row)
                result["options"] = self._metadata.options(user_id)
                return result
            row, _ = analytical_page_view(
                module=workflow.value,
                project_id=project_id,
                workflow=workflow_row,
            )
            return row

    def run_status(self, *, project_slug: str, stage_id: WorkflowId) -> Presentation:
        with self._scope() as user_id:
            _, workflow = self._workflow(user_id=user_id, project_slug=project_slug)
            raw_stages = workflow.get("stages")
            if not isinstance(raw_stages, dict):
                return {"status": "failed", "error_code": "workflow_projection_invalid"}
            stage = raw_stages.get(stage_id.value)
            if not isinstance(stage, dict):
                return {"status": "failed", "error_code": "workflow_stage_missing"}
            projection = dict(cast(dict[str, object], stage))
            run_key = {
                WorkflowId.UNIVARIATE_STATISTICS: "univariate_run_id",
                WorkflowId.BIVARIATE_STATISTICS: "bivariate_run_id",
                WorkflowId.MULTIVARIATE_STATISTICS: "multivariate_run_id",
            }.get(stage_id)
            run_id = None if run_key is None else projection.get(run_key)
            if not isinstance(run_id, str):
                return projection
            if stage_id is WorkflowId.UNIVARIATE_STATISTICS:
                return self._research.univariate_status(user_id, run_id)
            if stage_id is WorkflowId.BIVARIATE_STATISTICS:
                return self._research.bivariate_status(user_id, run_id)
            return self._research.multivariate_status(user_id, run_id)

    def start_run(
        self,
        *,
        project_slug: str,
        stage_id: WorkflowId,
        command_key: str,
        settings: Mapping[str, object],
    ) -> Presentation:
        with self._scope() as user_id:
            if stage_id is WorkflowId.METADATA_BUILDER:
                action = settings.get("action")
                if action == "fetch_metadata":
                    row, task = self._metadata.start_metadata_fetch(user_id)
                    task()
                    return row
                if action == "create_project":
                    row = self._metadata.create_project_from_criteria(
                        user_id,
                        exchange=str(settings.get("exchange") or ""),
                        name=str(settings.get("name") or ""),
                        instrument_type=str(settings.get("instrument_type") or ""),
                        country=str(settings.get("country") or ""),
                        currency=str(settings.get("currency") or ""),
                        idempotency_key=command_key,
                    )
                    project = row.get("project")
                    result = dict(row)
                    if isinstance(project, dict) and isinstance(project.get("name"), str):
                        result["project_slug"] = self.slug(cast(str, project["name"]))
                    return result

            project_id, workflow = self._workflow(user_id=user_id, project_slug=project_slug)
            stages = workflow.get("stages")
            if not isinstance(stages, dict):
                raise HostedApplicationError(409, "workflow_projection_invalid")
            typed_stages = cast(dict[str, object], stages)
            if stage_id is WorkflowId.UNIVARIATE_STATISTICS:
                metadata_stage = typed_stages.get(WorkflowId.METADATA_BUILDER.value)
                if not isinstance(metadata_stage, dict):
                    raise HostedApplicationError(409, "metadata_stage_unavailable")
                selection_id = metadata_stage.get("metadata_selection_id")
                quote_run_id = metadata_stage.get("quote_run_id")
                if not isinstance(selection_id, str):
                    raise HostedApplicationError(409, "metadata_selection_unavailable")
                typed_quote_run_id = quote_run_id if isinstance(quote_run_id, str) else None
                row = self._research.start_univariate(user_id, selection_id, typed_quote_run_id)
                if row.get("status") == "running":
                    self._request_scope.spawn_after_commit(
                        user_id=user_id,
                        operation=lambda: self._research.complete_univariate(
                            user_id, selection_id, typed_quote_run_id
                        ),
                    )
                return row
            if stage_id is WorkflowId.BIVARIATE_STATISTICS:
                univariate_stage = typed_stages.get(WorkflowId.UNIVARIATE_STATISTICS.value)
                if not isinstance(univariate_stage, dict):
                    raise HostedApplicationError(409, "univariate_stage_unavailable")
                selection_id = univariate_stage.get("univariate_selection_id")
                if not isinstance(selection_id, str):
                    raise HostedApplicationError(409, "univariate_selection_unavailable")
                row = self._research.start_bivariate(user_id, selection_id)
                if row.get("status") == "running":
                    self._request_scope.spawn_after_commit(
                        user_id=user_id,
                        operation=lambda: self._research.complete_bivariate(user_id, selection_id),
                    )
                return row
            if stage_id is WorkflowId.MULTIVARIATE_STATISTICS:
                bivariate_stage = typed_stages.get(WorkflowId.BIVARIATE_STATISTICS.value)
                if not isinstance(bivariate_stage, dict):
                    raise HostedApplicationError(409, "bivariate_stage_unavailable")
                bivariate_run_id = bivariate_stage.get("bivariate_run_id")
                if not isinstance(bivariate_run_id, str):
                    raise HostedApplicationError(409, "bivariate_run_unavailable")
                row = self._research.start_multivariate(
                    user_id, project_id, bivariate_run_id, dict(settings)
                )
                run_id = row.get("run_id")
                if row.get("status") == "running" and isinstance(run_id, str):
                    self._request_scope.spawn_after_commit(
                        user_id=user_id,
                        operation=lambda: self._research.complete_multivariate(user_id, run_id),
                    )
                return row
            raise HostedApplicationError(409, "stage_not_runnable")

    def selection_settings(self, *, project_slug: str, stage_id: WorkflowId) -> Presentation:
        if stage_id is not WorkflowId.UNIVARIATE_STATISTICS:
            return {}
        with self._scope() as user_id:
            project_id = self._project_id(user_id=user_id, project_slug=project_slug)
            return self._projects.univariate_selection_settings(user_id, project_id)

    def multivariate_settings(self, *, project_slug: str) -> Presentation:
        with self._scope() as user_id:
            _, workflow = self._workflow(user_id=user_id, project_slug=project_slug)
            stages = workflow.get("stages")
            stage = stages.get(WorkflowId.MULTIVARIATE_STATISTICS.value) if isinstance(stages, dict) else None
            run_id = stage.get("multivariate_run_id") if isinstance(stage, dict) else None
            if not isinstance(run_id, str):
                return {"objective": "return_risk"}
            settings = self._research.multivariate_status(user_id, run_id).get("settings")
            return settings if isinstance(settings, dict) else {"objective": "return_risk"}

    def decision_section(self, *, project_slug: str, run_id: str, section_id: str) -> Presentation:
        del project_slug, section_id
        with self._scope() as user_id:
            return self._research.multivariate_artifacts(user_id, run_id)

    def universe_history(self, *, project_slug: str, stage_id: str) -> Presentation:
        with self._scope() as user_id:
            _, workflow = self._workflow(user_id=user_id, project_slug=project_slug)
            process_overview = workflow.get("process_overview")
            return {
                "stage_id": stage_id,
                "process_overview": process_overview if isinstance(process_overview, dict) else {},
            }
