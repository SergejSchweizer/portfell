"""Operations-worker execution for browser-requested shared metadata refreshes."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from portfell.config import runtime_eodhd_config
from portfell.fetch_all_metadata import fetch_all_metadata
from portfell.hosted_metadata_refresh_job_repository import (
    ClaimedMetadataRefresh,
    PostgresMetadataRefreshJobRepository,
)
from portfell.hosted_metadata_repository import MetadataRun, PostgresMetadataLifecycleRepository
from portfell.hosted_navigation_reconciler import PostgresNavigationReconciler
from portfell.hosted_worker_capacity import resolve_worker_concurrency
from portfell.http import EodhdClient
from portfell.shared_metadata_catalog import SharedMetadataCatalog


@dataclass(frozen=True)
class MetadataRefreshWorkerResult:
    """One bounded worker polling result."""

    claimed: bool
    succeeded: bool


class MetadataRefreshJobs(Protocol):
    def claim(self) -> ClaimedMetadataRefresh | None: ...

    def complete(self, claim: ClaimedMetadataRefresh, *, succeeded: bool) -> None: ...


class MetadataRuns(Protocol):
    def status(self, *, user_id: str, run_id: str) -> MetadataRun | None: ...

    def update(self, run: MetadataRun) -> MetadataRun: ...

    def set_revision(self, *, user_id: str, revision_id: str) -> None: ...


class MetadataClient(Protocol):
    def get_json(
        self, path: str, params: Mapping[str, str | int | float] | None = None
    ) -> object: ...


class MetadataRefreshWorker:
    """Consume durable metadata jobs using only the operations credential."""

    def __init__(
        self,
        *,
        jobs: MetadataRefreshJobs,
        runs: MetadataRuns,
        catalog: SharedMetadataCatalog,
        client: MetadataClient,
        cpu_count: Callable[[], int | None] = os.process_cpu_count,
        concurrency: int | None = None,
    ) -> None:
        self._jobs = jobs
        self._runs = runs
        self._catalog = catalog
        self._client = client
        self._cpu_count = cpu_count
        self._concurrency = concurrency

    def run_once(self) -> MetadataRefreshWorkerResult:
        claim = self._jobs.claim()
        if claim is None:
            return MetadataRefreshWorkerResult(False, False)
        try:
            self._refresh(claim)
        except Exception:
            self._fail(claim)
            self._jobs.complete(claim, succeeded=False)
            return MetadataRefreshWorkerResult(True, False)
        self._jobs.complete(claim, succeeded=True)
        return MetadataRefreshWorkerResult(True, True)

    def _refresh(self, claim: ClaimedMetadataRefresh) -> None:
        def progress(completed: int, total: int, skipped: int) -> None:
            current = self._require_run(claim)
            self._runs.update(
                MetadataRun(
                    current.metadata_run_id,
                    current.user_id,
                    "running",
                    total,
                    completed,
                    skipped,
                    round((completed / total) * 100) if total else 0,
                    current.summary,
                )
            )

        result = fetch_all_metadata(
            self._client,
            concurrency=resolve_worker_concurrency(
                self._cpu_count() or os.cpu_count(), configured_concurrency=self._concurrency
            ),
            on_progress=progress,
        )
        rows = self._catalog.publish(result.rows)
        current = self._require_run(claim)
        self._runs.set_revision(user_id=claim.user_id, revision_id=str(len(rows)))
        self._runs.update(
            MetadataRun(
                current.metadata_run_id,
                current.user_id,
                "succeeded",
                len(result.requested_exchanges),
                len(result.requested_exchanges),
                len(result.skipped_exchanges),
                100,
                {
                    "row_count": len(rows),
                    "exchange_count": len({str(row["source_exchange"]) for row in rows}),
                    "requested_exchange_count": len(result.requested_exchanges),
                    "skipped_exchanges": list(result.skipped_exchanges),
                },
            )
        )

    def _require_run(self, claim: ClaimedMetadataRefresh) -> MetadataRun:
        run = self._runs.status(user_id=claim.user_id, run_id=claim.metadata_run_id)
        if run is None:
            raise ValueError("metadata_refresh_run_not_found")
        return run

    def _fail(self, claim: ClaimedMetadataRefresh) -> None:
        current = self._runs.status(user_id=claim.user_id, run_id=claim.metadata_run_id)
        if current is None:
            return
        self._runs.update(
            MetadataRun(
                current.metadata_run_id,
                current.user_id,
                "failed",
                current.total,
                current.completed,
                current.skipped_exchange_count,
                current.percent,
                {**current.summary, "error_code": "eodhd_metadata_unavailable"},
            )
        )


def build_metadata_refresh_worker(
    connection: object,
    *,
    shared_data_root: Path,
    operations_token: str,
    concurrency: int | None = None,
) -> MetadataRefreshWorker:
    """Compose a worker without making API processes shared-store writers."""

    jobs = PostgresMetadataRefreshJobRepository(connection)  # type: ignore[arg-type]
    runs = PostgresMetadataLifecycleRepository(
        connection,  # type: ignore[arg-type]
        navigation_refresher=PostgresNavigationReconciler(
            connection  # type: ignore[arg-type]
        ).reconcile,
    )
    return MetadataRefreshWorker(
        jobs=jobs,
        runs=runs,
        catalog=SharedMetadataCatalog(shared_data_root),
        client=EodhdClient(runtime_eodhd_config(operations_token)),
        concurrency=concurrency,
    )
