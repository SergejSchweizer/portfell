from __future__ import annotations

from dataclasses import replace

import pytest

from portfell.entitlements import ProviderDownloadRun
from portfell.hosted_download_run_repository import (
    DownloadRunRepositoryError,
    PostgresDownloadRunRepository,
)


class _Cursor:
    def __init__(self, row: tuple[object, ...] | None = None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class _Connection:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self._row = row

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        if "select download_run_id::text" in sql:
            return _Cursor(self._row)
        return _Cursor()


def _run() -> ProviderDownloadRun:
    return ProviderDownloadRun(
        download_run_id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000002",
        credential_id="00000000-0000-0000-0000-000000000003",
        provider="eodhd",
        status="partial",
        returned_observation_ids=("observation-1", "observation-2"),
        request_hash="request-hash",
        requested_scope={"symbols": ["AAA", "BBB"]},
    )


def _row(run: ProviderDownloadRun) -> tuple[object, ...]:
    return (
        run.download_run_id,
        run.user_id,
        run.credential_id,
        run.provider,
        run.status,
        {"returned_observation_ids": list(run.returned_observation_ids)},
        run.request_hash,
        run.requested_scope,
    )


def test_postgres_download_run_repository_persists_parameterized_scope_and_manifest() -> None:
    run = _run()
    connection = _Connection(_row(run))

    assert PostgresDownloadRunRepository(connection).create(run) == run

    statements = "\n".join(statement for statement, _ in connection.calls)
    assert connection.calls[0] == (
        "select set_config(%s, %s, true)",
        ("portfell.current_user_id", run.user_id),
    )
    assert "on conflict (user_id, request_hash) do nothing" in statements
    insert_parameters = connection.calls[1][1]
    assert insert_parameters[-2] == '{"symbols":["AAA","BBB"]}'
    assert insert_parameters[-1] == '{"returned_observation_ids":["observation-1","observation-2"]}'


def test_postgres_download_run_repository_rejects_conflicting_idempotency_projection() -> None:
    run = _run()
    conflict = replace(run, status="failed")

    with pytest.raises(DownloadRunRepositoryError, match="download_run_request_conflict"):
        PostgresDownloadRunRepository(_Connection(_row(conflict))).create(run)


def test_postgres_download_run_repository_rejects_malformed_manifest_projection() -> None:
    run = _run()
    malformed_manifest: dict[str, object] = {}
    invalid: tuple[object, ...] = (
        run.download_run_id,
        run.user_id,
        run.credential_id,
        run.provider,
        run.status,
        malformed_manifest,
        run.request_hash,
        run.requested_scope,
    )

    with pytest.raises(DownloadRunRepositoryError, match="download_run_projection_invalid"):
        PostgresDownloadRunRepository(_Connection(invalid)).get(
            user_id=run.user_id, download_run_id=run.download_run_id
        )


def test_postgres_download_run_repository_rejects_invalid_download_projections() -> None:
    run = _run()
    invalid_status = (*_row(run)[:4], "unknown", *_row(run)[5:])
    with pytest.raises(DownloadRunRepositoryError, match="download_run_projection_invalid"):
        PostgresDownloadRunRepository(_Connection(invalid_status)).get(
            user_id=run.user_id, download_run_id=run.download_run_id
        )
    invalid_scope = (*_row(run)[:7], {1: "invalid"})
    with pytest.raises(DownloadRunRepositoryError, match="download_run_projection_invalid"):
        PostgresDownloadRunRepository(_Connection(invalid_scope)).get(
            user_id=run.user_id, download_run_id=run.download_run_id
        )
    invalid_observations = (*_row(run)[:5], {"returned_observation_ids": [""]}, *_row(run)[6:])
    with pytest.raises(DownloadRunRepositoryError, match="download_run_projection_invalid"):
        PostgresDownloadRunRepository(_Connection(invalid_observations)).get(
            user_id=run.user_id, download_run_id=run.download_run_id
        )
    invalid_length: tuple[object, ...] = _row(run)[:-1]
    with pytest.raises(DownloadRunRepositoryError, match="download_run_projection_invalid"):
        PostgresDownloadRunRepository(_Connection(invalid_length)).get(
            user_id=run.user_id, download_run_id=run.download_run_id
        )


def test_postgres_download_run_repository_rejects_missing_idempotency_projection() -> None:
    run = _run()

    with pytest.raises(DownloadRunRepositoryError, match="download_run_not_found"):
        PostgresDownloadRunRepository(_Connection(None)).create(run)
