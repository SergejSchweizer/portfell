"""Local-only provider download run repository adapter."""

from __future__ import annotations

from portfell.entitlements import ProviderDownloadRun
from portfell.hosted_api_state import HostedApiState
from portfell.hosted_download_run_repository import (
    DownloadRunRepository,
    DownloadRunRepositoryError,
)


class LocalDownloadRunRepository(DownloadRunRepository):
    """Persist local-mode provider download runs in the development-state adapter."""

    def __init__(self, state: HostedApiState) -> None:
        self._state = state

    def create(self, run: ProviderDownloadRun) -> ProviderDownloadRun:
        existing = next(
            (
                candidate
                for candidate in self._state.downloads_by_id.values()
                if candidate.user_id == run.user_id and candidate.request_hash == run.request_hash
            ),
            None,
        )
        if existing is not None:
            if existing != run:
                raise DownloadRunRepositoryError("download_run_request_conflict")
            return existing
        self._state.downloads_by_id[run.download_run_id] = run
        return run

    def get(self, *, user_id: str, download_run_id: str) -> ProviderDownloadRun | None:
        run = self._state.downloads_by_id.get(download_run_id)
        return run if run is not None and run.user_id == user_id else None
