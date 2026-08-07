"""Serialize hosted state through the local-workspace persistence adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from portfell.hosted_api_state import HostedApiState, ProjectRecord, SelectionRecord


def persist_local_workspace(state: HostedApiState) -> None:
    """Persist the durable subset of hosted state when a store is configured."""

    if state.workspace_store is None:
        return
    state.workspace_store.save(
        {
            "projects": [
                {"project_id": row.project_id, "user_id": row.user_id, "name": row.name}
                for row in state.projects_by_id.values()
            ],
            "selections": [
                {
                    "selection_id": row.selection_id,
                    "user_id": row.user_id,
                    "project_id": row.project_id,
                    "name": row.name,
                    "member_ids": list(row.member_ids),
                }
                for row in state.selections_by_id.values()
            ],
            "current_project_id_by_user": state.current_project_id_by_user,
            "current_metadata_selection_by_user": state.current_metadata_selection_by_user,
            "metadata_revisions_by_user": state.metadata_revisions_by_user,
        }
    )


def restore_local_workspace(state: HostedApiState, payload: Mapping[str, object]) -> None:
    """Restore the durable subset of hosted state from a validated payload."""

    projects = payload.get("projects", [])
    selections = payload.get("selections", [])
    if not isinstance(projects, list) or not isinstance(selections, list):
        raise ValueError("local workspace state has an invalid shape")
    for project in cast("list[object]", projects):
        if not isinstance(project, Mapping):
            raise ValueError("local workspace project is invalid")
        row = cast("Mapping[str, object]", project)
        project_id = _text(row, "project_id")
        state.projects_by_id[project_id] = ProjectRecord(
            project_id=project_id,
            user_id=_text(row, "user_id"),
            name=_text(row, "name"),
        )
    for selection in cast("list[object]", selections):
        if not isinstance(selection, Mapping):
            raise ValueError("local workspace selection is invalid")
        row = cast("Mapping[str, object]", selection)
        member_ids = row.get("member_ids")
        if not isinstance(member_ids, list):
            raise ValueError("local workspace selection members are invalid")
        member_values = cast("list[object]", member_ids)
        if not all(isinstance(value, str) for value in member_values):
            raise ValueError("local workspace selection members are invalid")
        selection_id = _text(row, "selection_id")
        state.selections_by_id[selection_id] = SelectionRecord(
            selection_id=selection_id,
            user_id=_text(row, "user_id"),
            project_id=_text(row, "project_id"),
            name=_text(row, "name"),
            member_ids=tuple(cast("list[str]", member_values)),
        )
    state.current_project_id_by_user = _string_map(payload.get("current_project_id_by_user", {}))
    state.current_metadata_selection_by_user = _string_map(
        payload.get("current_metadata_selection_by_user", {})
    )
    state.metadata_revisions_by_user = _string_map(payload.get("metadata_revisions_by_user", {}))


def _text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"local workspace {key} is invalid")
    return value


def _string_map(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("local workspace mapping is invalid")
    mapping = cast("Mapping[str, object]", value)
    if not all(isinstance(item, str) for item in mapping.values()):
        raise ValueError("local workspace mapping is invalid")
    return {key: cast(str, item) for key, item in mapping.items()}
