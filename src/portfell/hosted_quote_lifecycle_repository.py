"""Quote lifecycle port: durable run state and compact progress belong together."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Protocol, cast

from portfell.entitlements import ProviderDownloadRun
from portfell.hosted_api_state import HostedApiState
from portfell.hosted_download_run_repository import (
    DownloadRunConnection,
    PostgresDownloadRunRepository,
)
from portfell.table_io import JsonRow


class QuoteLifecycleRepository(Protocol):
    def create(self, run: ProviderDownloadRun, *, progress: JsonRow) -> ProviderDownloadRun: ...

    def get(self, *, user_id: str, run_id: str) -> ProviderDownloadRun | None: ...

    def progress(self, *, user_id: str, run_id: str) -> JsonRow | None: ...

    def update(self, run: ProviderDownloadRun, *, progress: JsonRow) -> ProviderDownloadRun: ...


class LocalQuoteLifecycleRepository:
    """Explicit local adapter retaining legacy dictionaries outside application services."""

    def __init__(self, state: HostedApiState) -> None:
        self._state = state

    def create(self, run: ProviderDownloadRun, *, progress: JsonRow) -> ProviderDownloadRun:
        existing = self._state.downloads_by_id.get(run.download_run_id)
        if existing is not None:
            return existing
        self._state.downloads_by_id[run.download_run_id] = run
        self._state.download_summaries_by_id[run.download_run_id] = dict(progress)
        return run

    def get(self, *, user_id: str, run_id: str) -> ProviderDownloadRun | None:
        run = self._state.downloads_by_id.get(run_id)
        return run if run is not None and run.user_id == user_id else None

    def progress(self, *, user_id: str, run_id: str) -> JsonRow | None:
        return (
            dict(self._state.download_summaries_by_id[run_id])
            if self.get(user_id=user_id, run_id=run_id) is not None
            and run_id in self._state.download_summaries_by_id
            else None
        )

    def update(self, run: ProviderDownloadRun, *, progress: JsonRow) -> ProviderDownloadRun:
        existing = self.get(user_id=run.user_id, run_id=run.download_run_id)
        if existing is None:
            raise ValueError("quote_run_not_found")
        self._state.downloads_by_id[run.download_run_id] = replace(run)
        self._state.download_summaries_by_id[run.download_run_id] = dict(progress)
        return run


class PostgresQuoteLifecycleRepository:
    """Durable quote lifecycle adapter delegating owned runs to PostgreSQL."""

    def __init__(self, connection: DownloadRunConnection) -> None:
        self._connection = connection
        self._runs = PostgresDownloadRunRepository(connection)

    def create(self, run: ProviderDownloadRun, *, progress: JsonRow) -> ProviderDownloadRun:
        created = self._runs.create(run)
        return self._runs.update(created, progress=progress)

    def get(self, *, user_id: str, run_id: str) -> ProviderDownloadRun | None:
        return self._runs.get(user_id=user_id, download_run_id=run_id)

    def progress(self, *, user_id: str, run_id: str) -> JsonRow | None:
        row = self._connection.execute(
            "select response_manifest from portfell_app.download_runs "
            "where download_run_id = %s::uuid and user_id = %s::uuid",
            (run_id, user_id),
        ).fetchone()
        if row is None or len(row) != 1 or not isinstance(row[0], dict):
            return None
        manifest = cast(Mapping[str, object], row[0])
        progress = manifest.get("progress")
        return dict(cast(Mapping[str, object], progress)) if isinstance(progress, Mapping) else None

    def update(self, run: ProviderDownloadRun, *, progress: JsonRow) -> ProviderDownloadRun:
        return self._runs.update(run, progress=progress)
