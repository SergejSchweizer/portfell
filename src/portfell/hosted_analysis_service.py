"""Hosted portfolio-analysis application service."""

from __future__ import annotations

from portfell.hosted_api_serializers import analysis_row
from portfell.hosted_api_service_support import opaque_id, stable_hash
from portfell.hosted_api_state import AnalysisRecord
from portfell.hosted_research_ports import ResearchPersistencePort, ResearchRunRepository
from portfell.table_io import JsonRow


class HostedAnalysisService:
    """Own analysis idempotency and result retrieval."""

    def __init__(
        self, repository: ResearchRunRepository, persistence: ResearchPersistencePort
    ) -> None:
        self._repository = repository
        self._persistence = persistence

    def create(
        self,
        user_id: str,
        project_id: str,
        selection_id: str,
        settings: JsonRow,
        idempotency_key: str | None,
    ) -> JsonRow:
        selection = self._repository.metadata_selection(selection_id, user_id)
        self._repository.project(project_id, user_id)
        logical_hash = stable_hash(
            {
                "selection_id": selection.selection_id,
                "member_ids": list(selection.member_ids),
                "settings": settings,
            }
        )
        cached = self._repository.cached_id(user_id, "analysis", idempotency_key)
        if cached is not None:
            return {**analysis_row(self._repository.analysis(cached, user_id)), "cache_hit": True}
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
        self._repository.save_analysis(analysis)
        self._repository.remember_id(user_id, "analysis", idempotency_key, run_id)
        self._repository.audit(user_id, "analysis.create")
        self._persistence.persist()
        return {**analysis_row(analysis), "cache_hit": False}

    def analysis(self, user_id: str, run_id: str) -> AnalysisRecord:
        return self._repository.analysis(run_id, user_id)

    def status(self, user_id: str, run_id: str) -> JsonRow:
        return analysis_row(self.analysis(user_id, run_id))

    def metrics(self, user_id: str, run_id: str) -> JsonRow:
        return {"items": list(self.analysis(user_id, run_id).metrics)}

    def returns(self, user_id: str, run_id: str) -> JsonRow:
        return {"items": list(self.analysis(user_id, run_id).returns)}

    def weights(self, user_id: str, run_id: str) -> JsonRow:
        return {"items": list(self.analysis(user_id, run_id).weights)}

    def report(self, user_id: str, run_id: str) -> JsonRow:
        return self.analysis(user_id, run_id).report
