"""Shared domain operations for hosted application services."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from typing import cast

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_serializers import project_row
from portfell.hosted_api_state import (
    HostedApiState,
    ProjectRecord,
    SelectionRecord,
    UserOwnedRow,
)
from portfell.hosted_research_workflow import (
    FilterSelection,
    ResearchRun,
    create_full_univariate_selection,
)
from portfell.hosted_workspace_repository import persist_local_workspace
from portfell.table_io import JsonRow
from portfell.workflow_state import resolve_workflow

REMOVED_PROJECT_NAMES = frozenset({"Statistics Smoke"})


def opaque_id(kind: str, value: str) -> str:
    return f"{kind}_{uuid.uuid5(uuid.NAMESPACE_URL, value).hex}"


def stable_hash(payload: JsonRow) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def require_user_row[RowT: UserOwnedRow](
    rows: Mapping[str, RowT], row_id: str, user_id: str
) -> RowT:
    row = rows.get(row_id)
    if row is None or row.user_id != user_id:
        raise HostedApplicationError(404, "not_found")
    return row


def page(items: list[JsonRow], *, limit: int, offset: int) -> list[JsonRow]:
    if limit < 1 or limit > 500:
        raise HostedApplicationError(422, "invalid_limit")
    if offset < 0:
        raise HostedApplicationError(422, "invalid_offset")
    return items[offset : offset + limit]


def idempotent_response(
    state: HostedApiState, *, user_id: str, operation: str, idempotency_key: str | None
) -> str | None:
    if idempotency_key is None:
        return None
    return state.idempotency_refs.get((user_id, operation, idempotency_key))


def remember_idempotency(
    state: HostedApiState,
    user_id: str,
    operation: str,
    idempotency_key: str | None,
    row_id: str,
) -> None:
    if idempotency_key is not None:
        state.idempotency_refs[(user_id, operation, idempotency_key)] = row_id


def audit(state: HostedApiState, user_id: str, action: str) -> None:
    state.audit_events.append({"user_id": user_id, "action": action})
    persist_local_workspace(state)


def projects_for_user(state: HostedApiState, user_id: str) -> list[ProjectRecord]:
    return sorted(
        (project for project in state.projects_by_id.values() if project.user_id == user_id),
        key=lambda project: (project.name.casefold(), project.project_id),
    )


def current_project(state: HostedApiState, user_id: str) -> ProjectRecord | None:
    project_id = state.current_project_id_by_user.get(user_id)
    project = state.projects_by_id.get(project_id) if project_id is not None else None
    if project is not None and project.user_id == user_id:
        return project
    projects = projects_for_user(state, user_id)
    if not projects:
        state.current_project_id_by_user.pop(user_id, None)
        return None
    state.current_project_id_by_user[user_id] = projects[0].project_id
    return projects[0]


def set_current_project(state: HostedApiState, user_id: str, project_id: str) -> None:
    require_user_row(state.projects_by_id, project_id, user_id)
    state.current_project_id_by_user[user_id] = project_id


def selection_for_project(state: HostedApiState, project_id: str, user_id: str) -> SelectionRecord:
    current_selection_id = state.current_metadata_selection_by_user.get(user_id)
    current_selection = (
        state.selections_by_id.get(current_selection_id)
        if current_selection_id is not None
        else None
    )
    if (
        current_selection is not None
        and current_selection.user_id == user_id
        and current_selection.project_id == project_id
    ):
        return current_selection
    for selection in state.selections_by_id.values():
        if selection.project_id == project_id and selection.user_id == user_id:
            return selection
    raise HostedApplicationError(404, "not_found")


def project_data_loaded(state: HostedApiState, project_id: str, user_id: str) -> bool:
    operation = f"fetch-all-quotes:{project_id}"
    for (stored_user_id, stored_operation, _), run_id in state.idempotency_refs.items():
        if stored_user_id != user_id or stored_operation != operation:
            continue
        run = state.downloads_by_id.get(run_id)
        if run is not None and run.status == "succeeded":
            return True
    return False


def project_with_selection_row(
    state: HostedApiState, project: ProjectRecord, user_id: str
) -> JsonRow:
    try:
        selection = selection_for_project(state, project.project_id, user_id)
    except HostedApplicationError:
        return {**project_row(project), "selected_count": 0, "data_loaded": False}
    return {
        **project_row(project),
        "selection_id": selection.selection_id,
        "selected_count": _unique_member_isin_count(selection.member_ids),
        "data_loaded": project_data_loaded(state, project.project_id, user_id),
    }


def remove_discontinued_projects(state: HostedApiState, user_id: str) -> None:
    project_ids = {
        project_id
        for project_id, project in state.projects_by_id.items()
        if project.user_id == user_id and project.name in REMOVED_PROJECT_NAMES
    }
    if not project_ids:
        return
    state.projects_by_id = {
        row_id: row for row_id, row in state.projects_by_id.items() if row_id not in project_ids
    }
    state.selections_by_id = {
        row_id: row
        for row_id, row in state.selections_by_id.items()
        if row.project_id not in project_ids or row.user_id != user_id
    }
    state.analyses_by_id = {
        row_id: row
        for row_id, row in state.analyses_by_id.items()
        if row.project_id not in project_ids or row.user_id != user_id
    }


def project_context_row(state: HostedApiState, user_id: str) -> JsonRow:
    remove_discontinued_projects(state, user_id)
    project = current_project(state, user_id)
    projects = [
        project_with_selection_row(state, item, user_id)
        for item in projects_for_user(state, user_id)
    ]
    current = None if project is None else project_with_selection_row(state, project, user_id)
    return {
        "current_project_id": None if project is None else project.project_id,
        "current_project": current,
        "projects": projects,
    }


def _quote_run_id(
    state: HostedApiState, project_id: str, selection: SelectionRecord, user_id: str
) -> str | None:
    active_request_hash = stable_hash(
        {
            "project_id": project_id,
            "selection_id": selection.selection_id,
            "member_ids": list(selection.member_ids),
        }
    )
    active_run_id = opaque_id("fetch-all-quotes", f"{user_id}:{active_request_hash}")
    active_run = state.downloads_by_id.get(active_run_id)
    if active_run is not None and active_run.user_id == user_id and active_run.status == "running":
        return active_run_id
    operation = f"fetch-all-quotes:{project_id}"
    run_ids = sorted(
        run_id
        for (stored_user, stored_operation, _), run_id in state.idempotency_refs.items()
        if stored_user == user_id
        and stored_operation == operation
        and run_id in state.downloads_by_id
        and state.downloads_by_id[run_id].status == "succeeded"
    )
    return run_ids[0] if run_ids else None


def _univariate_run(
    state: HostedApiState, quote_run_id: str | None, user_id: str
) -> ResearchRun | None:
    run_ids = sorted(
        run_id
        for run_id, stored_quote_run_id in state.quote_run_by_univariate_run_id.items()
        if stored_quote_run_id == quote_run_id
        and run_id in state.univariate_runs_by_id
        and state.univariate_runs_by_id[run_id].user_id == user_id
    )
    return state.univariate_runs_by_id[run_ids[0]] if run_ids else None


def _filter_selection(
    state: HostedApiState, run_id: str | None, user_id: str
) -> FilterSelection | None:
    current_id = state.current_filter_selection_by_user.get(user_id)
    if current_id is not None:
        selection = state.filter_selections_by_id.get(current_id)
        if selection is not None and selection.source_run_id == run_id:
            return selection
    ids = sorted(
        row.selection_id
        for row in state.filter_selections_by_id.values()
        if row.source_run_id == run_id and row.user_id == user_id
    )
    return state.filter_selections_by_id[ids[0]] if ids else None


def _bivariate_run(
    state: HostedApiState, selection: FilterSelection | None, user_id: str
) -> ResearchRun | None:
    if selection is None:
        return None
    source_id = stable_hash(
        {"selection_id": selection.selection_id, "members": list(selection.member_ids)}
    )
    runs = sorted(
        (
            run
            for run in state.bivariate_runs_by_id.values()
            if run.user_id == user_id and run.source_id == source_id
        ),
        key=lambda run: run.run_id,
    )
    return runs[0] if runs else None


def workflow_row(
    state: HostedApiState,
    user_id: str,
    project_id: str | None,
    *,
    metadata_downloaded_isins: int | None = None,
) -> JsonRow:
    selection = None
    if project_id is not None:
        try:
            selection = selection_for_project(state, project_id, user_id)
        except HostedApplicationError:
            selection = None
    if selection is None:
        return {
            "stages": resolve_workflow(
                metadata_revision_id=None, metadata_selection_id=None, quote_run_id=None
            )
        }
    quote_run_id = _quote_run_id(state, selection.project_id, selection, user_id)
    metadata_revision_id = state.metadata_revisions_by_user.get(
        user_id, opaque_id("metadata-revision", selection.selection_id)
    )
    univariate_run = _univariate_run(state, quote_run_id, user_id)
    selected_univariate_rows = (
        ()
        if univariate_run is None
        else _apply_univariate_selection_settings(
            univariate_run.rows,
            state.univariate_selection_settings_by_project.get(selection.project_id, {}),
        )
    )
    filtered = _filter_selection(
        state, None if univariate_run is None else univariate_run.run_id, user_id
    )
    if univariate_run is not None and univariate_run.status == "complete" and filtered is None:
        filtered = create_full_univariate_selection(user_id=user_id, run=univariate_run)
        state.filter_selections_by_id.setdefault(filtered.selection_id, filtered)
        state.current_filter_selection_by_user[user_id] = filtered.selection_id
        persist_local_workspace(state)
    bivariate_run = _bivariate_run(state, filtered, user_id)
    return {
        "stages": resolve_workflow(
            metadata_revision_id=metadata_revision_id,
            metadata_selection_id=selection.selection_id,
            quote_run_id=quote_run_id,
            univariate_run_id=None if univariate_run is None else univariate_run.run_id,
            univariate_filter_selection_id=(None if filtered is None else filtered.selection_id),
            bivariate_run_id=None if bivariate_run is None else bivariate_run.run_id,
        ),
        "process_overview": {
            "metadata_downloaded_isins": (
                _unique_isin_count(state.all_isins_rows)
                if metadata_downloaded_isins is None
                else metadata_downloaded_isins
            ),
            "metadata_filter_isins": _unique_member_isin_count(selection.member_ids),
            "univariate_statistics_isins": (
                None if univariate_run is None else _unique_isin_count(selected_univariate_rows)
            ),
        },
    }


def _unique_isin_count(rows: tuple[JsonRow, ...]) -> int:
    return len(
        {str(row.get("isin", "")).strip() for row in rows if str(row.get("isin", "")).strip()}
    )


def _unique_member_isin_count(member_ids: tuple[str, ...]) -> int:
    return len({member_id.split(":", 1)[0] for member_id in member_ids if member_id})


def _apply_univariate_selection_settings(
    rows: tuple[JsonRow, ...], settings: JsonRow
) -> tuple[JsonRow, ...]:
    """Apply project dropdown selections to the completed univariate universe."""

    frequencies = settings.get("dividend_frequencies", [])
    ranges_by_metric = settings.get("statistic_ranges", {})
    selected_frequencies: set[str] = set()
    if isinstance(frequencies, list):
        selected_frequencies = {
            value for value in cast(list[object], frequencies) if isinstance(value, str)
        }
    selected_ranges: dict[str, tuple[Mapping[str, object], ...]] = {}
    if isinstance(ranges_by_metric, Mapping):
        for raw_metric, raw_ranges in cast(Mapping[object, object], ranges_by_metric).items():
            if not isinstance(raw_metric, str) or not isinstance(raw_ranges, list):
                continue
            selected_ranges[raw_metric] = tuple(
                cast(Mapping[str, object], item)
                for item in cast(list[object], raw_ranges)
                if isinstance(item, Mapping)
            )

    def includes_value(item: Mapping[str, object], value: float) -> bool:
        minimum = item.get("minimum")
        maximum = item.get("maximum")
        return (
            not isinstance(minimum, bool)
            and not isinstance(maximum, bool)
            and isinstance(minimum, int | float)
            and isinstance(maximum, int | float)
            and float(minimum) <= value <= float(maximum)
        )

    def matches(row: JsonRow) -> bool:
        frequency = str(row.get("distribution_frequency", "accumulating"))
        if frequency not in {"monthly", "quarterly", "semiannual", "annual", "irregular"}:
            frequency = "accumulating"
        if selected_frequencies and frequency not in selected_frequencies:
            return False
        for metric, ranges in selected_ranges.items():
            if not ranges:
                continue
            value = row.get(metric)
            if isinstance(value, bool) or not isinstance(value, int | float):
                return False
            if not any(includes_value(item, float(value)) for item in ranges):
                return False
        return True

    return tuple(row for row in rows if matches(row))
