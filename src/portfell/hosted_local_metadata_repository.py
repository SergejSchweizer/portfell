"""Explicit local-mode adapter for the metadata lifecycle repository port."""

from __future__ import annotations

from portfell.hosted_api_state import HostedApiState
from portfell.hosted_metadata_repository import MetadataRun


class LocalMetadataLifecycleRepository:
    """Keep legacy dictionaries isolated behind the local runtime adapter."""

    def __init__(self, state: HostedApiState) -> None:
        self._state = state

    def create(self, run: MetadataRun) -> MetadataRun:
        self._state.metadata_runs_by_id.setdefault(run.metadata_run_id, _row(run))
        return run

    def status(self, *, user_id: str, run_id: str) -> MetadataRun | None:
        row = self._state.metadata_runs_by_id.get(run_id)
        if row is None or row.get("user_id") != user_id:
            return None
        return MetadataRun(
            run_id,
            user_id,
            str(row["status"]),
            int(row.get("total", 0)),
            int(row.get("completed", 0)),
            int(row.get("skipped_exchange_count", 0)),
            int(row.get("percent", 0)),
            dict(row),
        )

    def update(self, run: MetadataRun) -> MetadataRun:
        self._state.metadata_runs_by_id[run.metadata_run_id] = _row(run)
        return run

    def set_revision(self, *, user_id: str, revision_id: str) -> None:
        self._state.metadata_revisions_by_user[user_id] = revision_id

    def revision(self, *, user_id: str) -> str | None:
        return self._state.metadata_revisions_by_user.get(user_id)

    def idempotent_response(
        self, *, user_id: str, operation: str, key: str, request_hash: str
    ) -> str | None:
        return self._state.idempotency_refs.get((user_id, operation, key))

    def remember_idempotency(
        self, *, user_id: str, operation: str, key: str, request_hash: str, response_ref: str
    ) -> None:
        self._state.idempotency_refs[(user_id, operation, key)] = response_ref


def _row(run: MetadataRun) -> dict[str, object]:
    return {
        **run.summary,
        "metadata_run_id": run.metadata_run_id,
        "user_id": run.user_id,
        "status": run.status,
        "total": run.total,
        "completed": run.completed,
        "skipped_exchange_count": run.skipped_exchange_count,
        "percent": run.percent,
    }
