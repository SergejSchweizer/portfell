from __future__ import annotations

from datetime import date
from typing import Any

from portfell.durable_job_repository import ClaimedJob
from portfell.hosted_project_bootstrap_worker import ProjectBootstrapWorker
from portfell.shared_market_data import SharedMarketDataStore


class _Jobs:
    def __init__(self, jobs: tuple[ClaimedJob, ...]) -> None:
        self._jobs = jobs
        self.progress: list[tuple[int, int]] = []
        self.completed: list[tuple[str, str | None]] = []

    def claim(self, *, worker_id: str, batch_size: int) -> tuple[ClaimedJob, ...]:
        assert worker_id == "worker-1"
        assert batch_size == 1
        return self._jobs

    def update_progress(
        self, *, job_id: str, lease_token: str, completed_units: int, total_units: int
    ) -> None:
        assert (job_id, lease_token) == ("job-1", "lease-1")
        self.progress.append((completed_units, total_units))

    def complete(
        self, *, job_id: str, lease_token: str, status: str, terminal_code: str | None = None
    ) -> None:
        assert (job_id, lease_token) == ("job-1", "lease-1")
        self.completed.append((status, terminal_code))


def _job(kind: str = "project_initial_fill") -> ClaimedJob:
    return ClaimedJob("job-1", "user-1", "project-1", kind, "hash-1", "selection-1", 0, "lease-1")


def test_worker_refreshes_only_the_claimed_exact_selection(tmp_path: Any) -> None:
    jobs = _Jobs((_job(),))
    requested: list[str] = []
    worker = ProjectBootstrapWorker(
        jobs=jobs,
        members_for_selection=lambda user_id, selection_id: (
            "IE0000000001:XETRA:ONE",
        )
        if (user_id, selection_id) == ("user-1", "selection-1")
        else (),
        store=SharedMarketDataStore(tmp_path),
        fetch=lambda request: requested.append(
            f"{request.listing.isin}:{request.listing.exchange}:{request.listing.code}"
        )
        or (),
        end_date=date(2026, 8, 11),
        concurrency=1,
    )

    result = worker.run_once(worker_id="worker-1")

    assert result.claimed_count == result.succeeded_count == 1
    assert result.failed_count == 0
    assert requested == ["IE0000000001:XETRA:ONE"] * 3
    assert jobs.progress == [(0, 1), (1, 1)]
    assert jobs.completed == [("succeeded", None)]


def test_worker_marks_the_claimed_bootstrap_failed_without_provider_access(tmp_path: Any) -> None:
    jobs = _Jobs((_job(),))
    worker = ProjectBootstrapWorker(
        jobs=jobs,
        members_for_selection=lambda _user_id, _selection_id: (),
        store=SharedMarketDataStore(tmp_path),
        fetch=lambda _request: (_ for _ in ()).throw(AssertionError("must not fetch")),
        end_date=date(2026, 8, 11),
        concurrency=1,
    )

    result = worker.run_once(worker_id="worker-1")

    assert (result.claimed_count, result.succeeded_count, result.failed_count) == (1, 0, 1)
    assert jobs.completed == [("failed", "initial_fill_failed")]
