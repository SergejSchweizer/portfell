"""Local-only immutable selection repository adapter."""

from __future__ import annotations

from portfell.hosted_api_state import HostedApiState, SelectionRecord
from portfell.hosted_repository_importer import TenantImportError, TenantSelection
from portfell.hosted_selection_repository import SelectionRepository


class LocalSelectionRepository(SelectionRepository):
    """Persist local-mode selections in the explicit development-state adapter."""

    def __init__(self, state: HostedApiState) -> None:
        self._state = state

    def create(self, selection: TenantSelection) -> TenantSelection:
        existing = self.for_project(project_id=selection.project_id, user_id=selection.user_id)
        if existing is not None and existing != selection:
            raise TenantImportError("project_membership_immutable")
        record = SelectionRecord(
            selection.selection_id,
            selection.user_id,
            selection.project_id,
            selection.name,
            selection.member_ids,
            selection.metadata_builder_predicates,
        )
        self._state.selections_by_id.setdefault(selection.selection_id, record)
        return selection

    def for_project(self, *, project_id: str, user_id: str) -> TenantSelection | None:
        selection_id = self._state.current_metadata_selection_by_user.get(user_id)
        current = self._state.selections_by_id.get(selection_id or "")
        if current is not None and current.project_id == project_id and current.user_id == user_id:
            return self._tenant_selection(current)
        selections = sorted(
            (
                selection
                for selection in self._state.selections_by_id.values()
                if selection.project_id == project_id and selection.user_id == user_id
            ),
            key=lambda selection: selection.selection_id,
        )
        return self._tenant_selection(selections[0]) if selections else None

    def by_id(self, *, selection_id: str, user_id: str) -> TenantSelection | None:
        selection = self._state.selections_by_id.get(selection_id)
        if selection is None or selection.user_id != user_id:
            return None
        return self._tenant_selection(selection)

    @staticmethod
    def _tenant_selection(selection: SelectionRecord) -> TenantSelection:
        return TenantSelection(
            selection.selection_id,
            selection.project_id,
            selection.user_id,
            selection.name,
            selection.member_ids,
            selection.metadata_builder_predicates,
        )
