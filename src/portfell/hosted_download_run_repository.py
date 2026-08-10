"""PostgreSQL repository for user-scoped provider download runs."""

from __future__ import annotations

import json
from typing import Protocol, cast

from portfell.entitlements import ProviderDownloadRun, RunStatus
from portfell.hosted_catalog import set_authenticated_user_sql
from portfell.table_io import JsonRow


class DownloadRunRepositoryError(ValueError):
    """Raised when a stored download-run projection violates its contract."""


class DownloadRunRepository(Protocol):
    """Persist and read user-owned provider download runs."""

    def create(self, run: ProviderDownloadRun) -> ProviderDownloadRun:
        """Create or return one idempotent provider download run."""

        ...

    def get(self, *, user_id: str, download_run_id: str) -> ProviderDownloadRun | None:
        """Read one owned provider download run."""

        ...


class DownloadRunCursor(Protocol):
    """Minimal PostgreSQL result boundary for download-run queries."""

    def fetchone(self) -> tuple[object, ...] | None: ...


class DownloadRunConnection(Protocol):
    """Parameterized connection boundary for owned download-run commands."""

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> DownloadRunCursor: ...


class PostgresDownloadRunRepository:
    """Persist and read provider download runs after transaction-local RLS binding."""

    def __init__(self, connection: DownloadRunConnection) -> None:
        self._connection = connection

    def create(self, run: ProviderDownloadRun) -> ProviderDownloadRun:
        """Create one idempotent user request or return its existing equivalent run."""

        self._bind_user(run.user_id)
        self._connection.execute(
            """
insert into portfell_app.download_runs (
    download_run_id, user_id, credential_id, provider, request_hash, status,
    requested_scope, response_manifest
) values (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, %s::jsonb)
on conflict (user_id, request_hash) do nothing
""",
            (
                run.download_run_id,
                run.user_id,
                run.credential_id,
                run.provider,
                run.request_hash,
                run.status,
                _json(run.requested_scope),
                _json({"returned_observation_ids": list(run.returned_observation_ids)}),
            ),
        )
        existing = self.get_by_request_hash(user_id=run.user_id, request_hash=run.request_hash)
        if existing is None:
            raise DownloadRunRepositoryError("download_run_not_found")
        if existing != run:
            raise DownloadRunRepositoryError("download_run_request_conflict")
        return existing

    def get(self, *, user_id: str, download_run_id: str) -> ProviderDownloadRun | None:
        """Read one owned download run by its stable identifier."""

        self._bind_user(user_id)
        row = self._connection.execute(
            _DOWNLOAD_RUN_SELECT + "where download_run_id = %s::uuid",
            (download_run_id,),
        ).fetchone()
        return None if row is None else _download_run(row)

    def get_by_request_hash(self, *, user_id: str, request_hash: str) -> ProviderDownloadRun | None:
        """Read one owned idempotency key projection."""

        self._bind_user(user_id)
        row = self._connection.execute(
            _DOWNLOAD_RUN_SELECT + "where request_hash = %s",
            (request_hash,),
        ).fetchone()
        return None if row is None else _download_run(row)

    def _bind_user(self, user_id: str) -> None:
        self._connection.execute(*set_authenticated_user_sql(user_id))


_DOWNLOAD_RUN_SELECT = """
select download_run_id::text, user_id::text, credential_id::text, provider, status,
       response_manifest, request_hash, requested_scope
from portfell_app.download_runs
"""


def _json(value: JsonRow) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _download_run(row: tuple[object, ...]) -> ProviderDownloadRun:
    if len(row) != 8:
        raise DownloadRunRepositoryError("download_run_projection_invalid")
    (
        download_run_id,
        user_id,
        credential_id,
        provider,
        status,
        response_manifest,
        request_hash,
        requested_scope,
    ) = row
    identifiers = (download_run_id, user_id, credential_id, provider, status, request_hash)
    typed_identifiers = _non_empty_strings(identifiers)
    (
        typed_download_run_id,
        typed_user_id,
        typed_credential_id,
        typed_provider,
        typed_status,
        typed_request_hash,
    ) = typed_identifiers
    if typed_status not in {"planned", "running", "succeeded", "failed", "partial"}:
        raise DownloadRunRepositoryError("download_run_projection_invalid")
    manifest = _json_row(response_manifest)
    observation_ids = manifest.get("returned_observation_ids")
    if not isinstance(observation_ids, list):
        raise DownloadRunRepositoryError("download_run_projection_invalid")
    typed_observation_ids = _non_empty_strings(cast(list[object], observation_ids))
    return ProviderDownloadRun(
        download_run_id=typed_download_run_id,
        user_id=typed_user_id,
        credential_id=typed_credential_id,
        provider=typed_provider,
        status=cast(RunStatus, typed_status),
        returned_observation_ids=typed_observation_ids,
        request_hash=typed_request_hash,
        requested_scope=_json_row(requested_scope),
    )


def _json_row(value: object) -> JsonRow:
    if not isinstance(value, dict):
        raise DownloadRunRepositoryError("download_run_projection_invalid")
    mapping = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise DownloadRunRepositoryError("download_run_projection_invalid")
    return cast(JsonRow, mapping)


def _non_empty_strings(values: tuple[object, ...] | list[object]) -> tuple[str, ...]:
    typed_values: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value:
            raise DownloadRunRepositoryError("download_run_projection_invalid")
        typed_values.append(value)
    return tuple(typed_values)
