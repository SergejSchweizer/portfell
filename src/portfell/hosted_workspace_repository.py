"""Serialize hosted state through the local-workspace persistence adapter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import cast

from portfell.entitlements import ProviderDownloadRun, RunStatus
from portfell.hosted_api_state import HostedApiState, ProjectRecord, SelectionRecord
from portfell.hosted_research_workflow import ResearchRun
from portfell.hosted_research_workflow import RunStatus as ResearchRunStatus


def persist_local_workspace(state: HostedApiState) -> None:
    """Persist local-workspace state and completed quote-run inputs when configured."""

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
            "quote_runs": [
                {
                    "download_run_id": row.download_run_id,
                    "user_id": row.user_id,
                    "credential_id": row.credential_id,
                    "provider": row.provider,
                    "status": row.status,
                    "returned_observation_ids": list(row.returned_observation_ids),
                    "request_hash": row.request_hash,
                }
                for row in state.downloads_by_id.values()
            ],
            "quote_run_summaries": state.download_summaries_by_id,
            "quote_rows_by_run_id": {
                run_id: list(rows) for run_id, rows in state.quote_rows_by_run_id.items()
            },
            "univariate_runs": [
                {
                    "run_id": run.run_id,
                    "user_id": run.user_id,
                    "source_id": run.source_id,
                    "status": run.status,
                    "rows": list(run.rows),
                    "total": run.total,
                    "completed": run.completed,
                    "failed": run.failed,
                    "quote_run_id": state.quote_run_by_univariate_run_id.get(run.run_id, ""),
                }
                for run in state.univariate_runs_by_id.values()
            ],
            "idempotency_refs": [
                {
                    "user_id": user_id,
                    "operation": operation,
                    "idempotency_key": idempotency_key,
                    "row_id": row_id,
                }
                for (user_id, operation, idempotency_key), row_id in state.idempotency_refs.items()
            ],
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
    _restore_quote_runs(state, payload)
    _restore_univariate_runs(state, payload)


def _restore_quote_runs(state: HostedApiState, payload: Mapping[str, object]) -> None:
    """Restore durable quote results; interrupted work is explicitly retryable."""

    quote_runs = _object_list(payload.get("quote_runs", []), "quote runs")
    for item in quote_runs:
        row = _mapping(item, "quote run")
        observation_ids = _string_list(
            row.get("returned_observation_ids"), "quote run observations"
        )
        status = _text(row, "status")
        if status not in {"planned", "running", "succeeded", "failed", "partial"}:
            raise ValueError("local workspace quote run status is invalid")
        run = ProviderDownloadRun(
            download_run_id=_text(row, "download_run_id"),
            user_id=_text(row, "user_id"),
            credential_id=_text(row, "credential_id"),
            provider=_text(row, "provider"),
            status=cast(RunStatus, status),
            returned_observation_ids=tuple(observation_ids),
            request_hash=_text(row, "request_hash"),
        )
        # A background task cannot survive a container restart. Do not restore it as active.
        state.downloads_by_id[run.download_run_id] = (
            replace(run, status="failed") if run.status == "running" else run
        )

    raw_summaries = payload.get("quote_run_summaries", {})
    if not isinstance(raw_summaries, Mapping):
        raise ValueError("local workspace quote run summaries are invalid")
    summaries = cast(Mapping[object, object], raw_summaries)
    state.download_summaries_by_id = {
        _text_key(run_id, "quote run summary"): dict(_mapping(summary, "quote run summary"))
        for run_id, summary in summaries.items()
    }
    for run_id, run in state.downloads_by_id.items():
        if run.status == "failed" and run_id in state.download_summaries_by_id:
            state.download_summaries_by_id[run_id] = {
                **state.download_summaries_by_id[run_id],
                "error_code": "quote_run_interrupted_by_restart",
            }

    raw_persisted_rows = payload.get("quote_rows_by_run_id", {})
    if not isinstance(raw_persisted_rows, Mapping):
        raise ValueError("local workspace quote rows are invalid")
    persisted_rows = cast(Mapping[object, object], raw_persisted_rows)
    state.quote_rows_by_run_id = {
        _text_key(run_id, "quote rows"): tuple(
            dict(_mapping(row, "quote row")) for row in _object_list(rows, "quote rows")
        )
        for run_id, rows in persisted_rows.items()
    }

    references = _object_list(payload.get("idempotency_refs", []), "idempotency refs")
    state.idempotency_refs = {
        (
            _text(row, "user_id"),
            _text(row, "operation"),
            _text(row, "idempotency_key"),
        ): _text(row, "row_id")
        for item in references
        for row in (_mapping(item, "idempotency ref"),)
    }


def _restore_univariate_runs(state: HostedApiState, payload: Mapping[str, object]) -> None:
    """Restore completed project-scoped statistics and their source quote run."""

    for item in _object_list(payload.get("univariate_runs", []), "univariate runs"):
        row = _mapping(item, "univariate run")
        status = _text(row, "status")
        if status not in {"running", "complete", "failed"}:
            raise ValueError("local workspace univariate run status is invalid")
        run = ResearchRun(
            run_id=_text(row, "run_id"),
            user_id=_text(row, "user_id"),
            source_id=_text(row, "source_id"),
            status=cast(ResearchRunStatus, "failed" if status == "running" else status),
            rows=tuple(
                dict(_mapping(value, "univariate statistic"))
                for value in _object_list(row.get("rows", []), "univariate statistics")
            ),
            total=_integer(row, "total"),
            completed=_integer(row, "completed"),
            failed=(_integer(row, "total") if status == "running" else _integer(row, "failed")),
        )
        quote_run_id = _text(row, "quote_run_id")
        state.univariate_runs_by_id[run.run_id] = run
        state.quote_run_by_univariate_run_id[run.run_id] = quote_run_id


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


def _object_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"local workspace {label} are invalid")
    return cast(list[object], value)


def _string_list(value: object, label: str) -> list[str]:
    values = _object_list(value, label)
    if not all(isinstance(item, str) and item for item in values):
        raise ValueError(f"local workspace {label} are invalid")
    return cast(list[str], values)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"local workspace {label} is invalid")
    return cast(Mapping[str, object], value)


def _text_key(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"local workspace {label} key is invalid")
    return value


def _integer(row: Mapping[str, object], key: str) -> int:
    value = row.get(key)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"local workspace {key} is invalid")
    return value
