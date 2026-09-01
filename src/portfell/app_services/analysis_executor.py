"""Single-process durable executor for staged analysis jobs."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Protocol

from portfell.app_services.research_compute import JsonRow
from portfell.app_state.contracts import AnalysisJobRecord
from portfell.app_state.errors import AppStateError


class AnalysisJobState(Protocol):
    def claim_job(self, job_id: str, *, stale_before: datetime) -> AnalysisJobRecord: ...

    def link_job_run(self, job_id: str, run_id: str) -> AnalysisJobRecord: ...

    def complete_job(
        self, job_id: str, *, status: str, failure_code: str | None = None
    ) -> AnalysisJobRecord: ...

    def list_analysis_jobs(
        self, *, stage: str | None = None, status: str | None = None, limit: int = 100
    ) -> tuple[AnalysisJobRecord, ...]: ...


JobRunner = Callable[[AnalysisJobRecord], JsonRow]


class AnalysisJobExecutor:
    """Own one top-level worker without making HTTP callers wait for computation."""

    def __init__(
        self,
        state: AnalysisJobState,
        runner: JobRunner,
        *,
        now: Callable[[], datetime] | None = None,
        stale_after: timedelta = timedelta(minutes=5),
        executor_factory: Callable[[], ThreadPoolExecutor] | None = None,
    ) -> None:
        self._state = state
        self._runner = runner
        self._now = now or (lambda: datetime.now(UTC))
        self._stale_after = stale_after
        self._executor_factory = executor_factory or (lambda: ThreadPoolExecutor(max_workers=1))
        self._executor: ThreadPoolExecutor | None = None
        self._futures: dict[str, Future[None]] = {}
        self._lock = Lock()
        self._closed = False

    def submit(self, job: AnalysisJobRecord) -> None:
        """Schedule an already-persisted job, without waiting for a compute slot."""
        with self._lock:
            if self._closed or job.job_id in self._futures:
                return
            if self._executor is None:
                self._executor = self._executor_factory()
            future = self._executor.submit(self._run, job.job_id)
            self._futures[job.job_id] = future
        future.add_done_callback(lambda _: self._forget(job.job_id))

    def recover(self) -> None:
        """Schedule only durable queued/stale work after process startup."""
        for status in ("queued", "running"):
            for job in self._state.list_analysis_jobs(status=status, limit=500):
                self.submit(job)

    def close(self) -> None:
        """Stop accepting new jobs and wait for the one owned worker to finish."""
        with self._lock:
            self._closed = True
            executor = self._executor
            self._executor = None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=False)

    def _run(self, job_id: str) -> None:
        try:
            job = self._state.claim_job(job_id, stale_before=self._now() - self._stale_after)
        except AppStateError:
            return
        try:
            result = self._runner(job)
            run_id = result.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                raise RuntimeError("analysis_run_missing")
            self._state.link_job_run(job_id, run_id)
            self._state.complete_job(job_id, status="succeeded")
        except Exception as error:
            self._complete_failed(job_id, error)

    def _complete_failed(self, job_id: str, error: Exception) -> None:
        failure_code = getattr(error, "code", None)
        code = (
            failure_code
            if isinstance(failure_code, str) and failure_code
            else "analysis_compute_failed"
        )
        try:
            self._state.complete_job(job_id, status="failed", failure_code=code)
        except AppStateError:
            return

    def _forget(self, job_id: str) -> None:
        with self._lock:
            self._futures.pop(job_id, None)


__all__ = ["AnalysisJobExecutor", "AnalysisJobState", "JobRunner"]
