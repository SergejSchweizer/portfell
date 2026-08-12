from __future__ import annotations

from contextlib import nullcontext
from datetime import date
from time import sleep
from typing import Any

from portfell.durable_job_repository import ClaimedJob
from portfell.hosted_project_bootstrap_worker import (
    PostgresSelectionMembers,
    ProjectBootstrapWorker,
)
from portfell.shared_market_data import SharedMarketDataStore


class _Jobs:
    def __init__(self, jobs: tuple[ClaimedJob, ...]) -> None:
        self._jobs = jobs
        self.progress: list[tuple[int, int]] = []
        self.failed_listing_counts: list[int] = []
        self.completed: list[tuple[str, str | None]] = []
        self.heartbeats: list[tuple[str, str]] = []

    def claim(self, *, worker_id: str, batch_size: int) -> tuple[ClaimedJob, ...]:
        assert worker_id == "worker-1"
        assert batch_size == 1
        return self._jobs

    def update_progress(
        self, *, job_id: str, lease_token: str, completed_units: int, total_units: int
    ) -> None:
        assert (job_id, lease_token) == ("job-1", "lease-1")
        self.progress.append((completed_units, total_units))

    def heartbeat(self, *, job_id: str, lease_token: str) -> None:
        self.heartbeats.append((job_id, lease_token))

    def set_initial_fill_failed_listing_count(
        self, *, job_id: str, user_id: str, failed_listing_count: int
    ) -> None:
        assert (job_id, user_id) == ("job-1", "user-1")
        self.failed_listing_counts.append(failed_listing_count)

    def complete(
        self, *, job_id: str, lease_token: str, status: str, terminal_code: str | None = None
    ) -> None:
        assert (job_id, lease_token) == ("job-1", "lease-1")
        self.completed.append((status, terminal_code))


class _SelectionCursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class _SelectionConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def transaction(self) -> Any:
        return nullcontext()

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _SelectionCursor:
        self.calls.append((sql, parameters))
        return _SelectionCursor([("IE0000000001", "XETRA", "ONE")])


def _job(kind: str = "project_initial_fill") -> ClaimedJob:
    return ClaimedJob("job-1", "user-1", "project-1", kind, "hash-1", "selection-1", 0, "lease-1")


def test_worker_refreshes_only_the_claimed_exact_selection(tmp_path: Any) -> None:
    jobs = _Jobs((_job(),))
    requested: list[str] = []
    worker = ProjectBootstrapWorker(
        jobs=jobs,
        members_for_selection=lambda user_id, selection_id: (
            ("IE0000000001:XETRA:ONE", "IE0000000002:XETRA:TWO")
            if (user_id, selection_id) == ("user-1", "selection-1")
            else ()
        ),
        store=SharedMarketDataStore(tmp_path),
        fetch=lambda request: (
            requested.append(
                f"{request.listing.isin}:{request.listing.exchange}:{request.listing.code}"
            )
            or ()
        ),
        end_date=date(2026, 8, 11),
        concurrency=1,
    )

    result = worker.run_once(worker_id="worker-1")

    assert result.claimed_count == result.succeeded_count == 1
    assert result.failed_count == 0
    assert requested == ["IE0000000001:XETRA:ONE"] * 3 + ["IE0000000002:XETRA:TWO"] * 3
    assert jobs.progress == [(0, 2), (1, 2), (2, 2), (2, 2)]
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
    assert jobs.failed_listing_counts == [0]


def test_worker_records_failed_isin_count_for_partial_refresh(tmp_path: Any) -> None:
    jobs = _Jobs((_job(),))
    worker = ProjectBootstrapWorker(
        jobs=jobs,
        members_for_selection=lambda _user_id, _selection_id: ("IE0000000001:XETRA:ONE",),
        store=SharedMarketDataStore(tmp_path),
        fetch=lambda _request: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
        end_date=date(2026, 8, 11),
        concurrency=1,
    )

    result = worker.run_once(worker_id="worker-1")

    assert result.failed_count == 1
    assert jobs.failed_listing_counts == [1]


def test_worker_renews_the_lease_while_a_provider_request_is_slow(tmp_path: Any) -> None:
    jobs = _Jobs((_job(),))
    worker = ProjectBootstrapWorker(
        jobs=jobs,
        members_for_selection=lambda _user_id, _selection_id: ("IE0000000001:XETRA:ONE",),
        store=SharedMarketDataStore(tmp_path),
        fetch=lambda _request: sleep(0.02) or (),
        end_date=date(2026, 8, 11),
        concurrency=1,
        heartbeat_interval_seconds=0.001,
    )

    result = worker.run_once(worker_id="worker-1")

    assert result.succeeded_count == 1
    assert jobs.heartbeats


def test_postgres_selection_reader_binds_the_claimed_user_before_reading_members() -> None:
    connection = _SelectionConnection()

    members = PostgresSelectionMembers(connection)("user-1", "selection-1")

    assert members == ("IE0000000001:XETRA:ONE",)
    assert connection.calls[0][1][1] == "user-1"
    assert "project_selection_members" in connection.calls[1][0]
