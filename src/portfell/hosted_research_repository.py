"""Repository adapter for hosted research application services."""

from __future__ import annotations

import uuid

from portfell.entitlements import ProviderDownloadRun
from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_service_support import (
    require_user_row,
)
from portfell.hosted_api_state import AnalysisRecord, HostedApiState, ProjectRecord, SelectionRecord
from portfell.hosted_audit_event_repository import AuditEventRepository, HostedAuditEvent
from portfell.hosted_idempotency_repository import (
    IdempotencyRepository,
    LocalIdempotencyRepository,
)
from portfell.hosted_local_audit_event_repository import LocalAuditEventRepository
from portfell.hosted_local_project_repository import LocalProjectRepository
from portfell.hosted_local_selection_repository import LocalSelectionRepository
from portfell.hosted_repository_importer import ProjectRepository
from portfell.hosted_research_workflow import ResearchRun, UnivariateSelection
from portfell.hosted_selection_repository import SelectionRepository, selection_record
from portfell.shared_market_data import SharedListingKey
from portfell.table_io import JsonRow


class HostedResearchRepository:
    """Encapsulate mutable hosted state behind user-scoped repository operations."""

    def __init__(
        self,
        state: HostedApiState,
        project_repository: ProjectRepository | None = None,
        selection_repository: SelectionRepository | None = None,
        idempotency_repository: IdempotencyRepository | None = None,
        audit_repository: AuditEventRepository | None = None,
    ) -> None:
        self._state = state
        self._projects = project_repository or LocalProjectRepository(state)
        self._selections = selection_repository or LocalSelectionRepository(state)
        self._idempotency = idempotency_repository or LocalIdempotencyRepository(state)
        self._audit_events = audit_repository or LocalAuditEventRepository(state)

    def metadata_selection(self, selection_id: str, user_id: str) -> SelectionRecord:
        selection = self._selections.by_id(selection_id=selection_id, user_id=user_id)
        if selection is None:
            raise HostedApplicationError(404, "not_found")
        return selection_record(selection)

    def quote_run(self, run_id: str, user_id: str) -> ProviderDownloadRun:
        return require_user_row(self._state.downloads_by_id, run_id, user_id)

    def quote_rows(self, run_id: str) -> tuple[JsonRow, ...]:
        run = self._state.downloads_by_id.get(run_id)
        store = self._state.shared_market_data_store
        if run is not None and store is not None:
            rows: list[JsonRow] = []
            for member_id in run.returned_observation_ids:
                rows.extend(store.read("quotes", SharedListingKey.from_member_id(member_id)))
            return tuple(rows)
        return self._state.quote_rows_by_run_id.get(run_id, ())

    def univariate_run(self, run_id: str, user_id: str) -> ResearchRun:
        return require_user_row(self._state.univariate_runs_by_id, run_id, user_id)

    def find_univariate_run(self, run_id: str, user_id: str) -> ResearchRun | None:
        run = self._state.univariate_runs_by_id.get(run_id)
        return run if run is not None and run.user_id == user_id else None

    def save_univariate_run(self, run: ResearchRun) -> None:
        self._state.univariate_runs_by_id[run.run_id] = run

    def delete_univariate_run(self, run_id: str) -> None:
        self._state.univariate_runs_by_id.pop(run_id, None)
        self._state.quote_run_by_univariate_run_id.pop(run_id, None)

    def bind_quote_run(self, univariate_run_id: str, quote_run_id: str) -> None:
        self._state.quote_run_by_univariate_run_id[univariate_run_id] = quote_run_id

    def bind_project_run(self, *, user_id: str, project_id: str, run_id: str) -> None:
        _ = user_id
        self._state.project_id_by_research_run[run_id] = project_id

    def project_id_for_run(self, *, user_id: str, run_id: str) -> str | None:
        project_id = self._state.project_id_by_research_run.get(run_id)
        if project_id is None:
            return None
        _ = user_id
        return project_id

    def quote_run_id(self, univariate_run_id: str) -> str:
        return self._state.quote_run_by_univariate_run_id.get(univariate_run_id, "")

    def univariate_selection(self, selection_id: str, user_id: str) -> UnivariateSelection:
        return require_user_row(self._state.univariate_selections_by_id, selection_id, user_id)

    def univariate_selections(self, user_id: str) -> tuple[UnivariateSelection, ...]:
        return tuple(
            selection
            for selection in self._state.univariate_selections_by_id.values()
            if selection.user_id == user_id
        )

    def save_univariate_selection(self, selection: UnivariateSelection) -> UnivariateSelection:
        return self._state.univariate_selections_by_id.setdefault(selection.selection_id, selection)

    def set_current_univariate_selection(self, user_id: str, selection_id: str) -> None:
        self._state.current_univariate_selection_by_user[user_id] = selection_id

    def bivariate_run(self, run_id: str, user_id: str) -> ResearchRun:
        return require_user_row(self._state.bivariate_runs_by_id, run_id, user_id)

    def find_bivariate_run(self, run_id: str, user_id: str) -> ResearchRun | None:
        run = self._state.bivariate_runs_by_id.get(run_id)
        return run if run is not None and run.user_id == user_id else None

    def save_bivariate_run(self, run: ResearchRun) -> None:
        self._state.bivariate_runs_by_id[run.run_id] = run

    def project(self, project_id: str, user_id: str) -> ProjectRecord:
        for project in self._projects.list_projects(user_id):
            if project.project_id == project_id:
                return ProjectRecord(project.project_id, project.user_id, project.name)
        raise HostedApplicationError(404, "not_found")

    def analysis(self, run_id: str, user_id: str) -> AnalysisRecord:
        return require_user_row(self._state.analyses_by_id, run_id, user_id)

    def save_analysis(self, analysis: AnalysisRecord) -> None:
        self._state.analyses_by_id[analysis.run_id] = analysis

    def cached_id(self, user_id: str, operation: str, key: str | None) -> str | None:
        return self._idempotency.lookup(
            user_id=user_id,
            operation=operation,
            key=key,
            request_hash=operation,
        )

    def remember_id(self, user_id: str, operation: str, key: str | None, row_id: str) -> None:
        self._idempotency.remember(
            user_id=user_id,
            operation=operation,
            key=key,
            request_hash=operation,
            response_ref=row_id,
        )

    def audit(self, user_id: str, action: str) -> None:
        self._audit_events.append(
            HostedAuditEvent(
                audit_event_id=str(uuid.uuid4()),
                user_id=user_id,
                event_type=action,
                subject_ref=f"user:{user_id}",
                metadata={},
            )
        )
