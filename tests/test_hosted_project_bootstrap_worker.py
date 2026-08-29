from __future__ import annotations

from contextlib import nullcontext
from datetime import date
from threading import Event, Lock
from time import sleep
from types import SimpleNamespace
from typing import Any

import pytest

import portfell.hosted_project_bootstrap_worker as bootstrap_worker_module
from portfell.durable_job_repository import ClaimedJob
from portfell.hosted_project_bootstrap_worker import (
    BootstrapWorkerResult,
    PostgresSelectionMembers,
    ProjectBootstrapWorker,
    build_parser,
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


def test_worker_serializes_progress_and_heartbeat_writes(tmp_path: Any) -> None:
    class ConcurrentJobs(_Jobs):
        def __init__(self) -> None:
            super().__init__((_job(),))
            self.concurrent_write_detected = False
            self._active_writes = 0
            self._write_lock = Lock()

        def _record_write(self) -> None:
            with self._write_lock:
                self._active_writes += 1
                self.concurrent_write_detected |= self._active_writes > 1
            sleep(0.005)
            with self._write_lock:
                self._active_writes -= 1

        def update_progress(
            self, *, job_id: str, lease_token: str, completed_units: int, total_units: int
        ) -> None:
            self._record_write()
            super().update_progress(
                job_id=job_id,
                lease_token=lease_token,
                completed_units=completed_units,
                total_units=total_units,
            )

        def heartbeat(self, *, job_id: str, lease_token: str) -> None:
            self._record_write()
            super().heartbeat(job_id=job_id, lease_token=lease_token)

    jobs = ConcurrentJobs()
    worker = ProjectBootstrapWorker(
        jobs=jobs,
        members_for_selection=lambda _user_id, _selection_id: (
            "IE0000000001:XETRA:ONE",
            "IE0000000002:XETRA:TWO",
        ),
        store=SharedMarketDataStore(tmp_path),
        fetch=lambda _request: (),
        end_date=date(2026, 8, 11),
        concurrency=2,
        heartbeat_interval_seconds=0.001,
    )

    result = worker.run_once(worker_id="worker-1")

    assert result.succeeded_count == 1
    assert not jobs.concurrent_write_detected


def test_postgres_selection_reader_binds_the_claimed_user_before_reading_members() -> None:
    connection = _SelectionConnection()

    members = PostgresSelectionMembers(connection)("user-1", "selection-1")

    assert members == ("IE0000000001:XETRA:ONE",)
    assert connection.calls[0][1][1] == "user-1"
    assert "project_selection_members" in connection.calls[1][0]


def test_worker_parser_uses_combined_metadata_and_initial_fill_mode() -> None:
    arguments = build_parser().parse_args([])

    assert arguments.once is False
    assert not hasattr(arguments, "metadata_only")


def test_worker_polls_metadata_while_an_initial_fill_is_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    initial_fill_started = Event()
    release_initial_fill = Event()
    metadata_calls: list[None] = []
    connections: list[Any] = [
        SimpleNamespace(close=lambda: None),
        SimpleNamespace(close=lambda: None),
    ]

    class MetadataWorker:
        def run_once(self) -> Any:
            metadata_calls.append(None)
            return SimpleNamespace(claimed=False, succeeded=False)

    class InitialFillWorker:
        def __init__(self, **_: Any) -> None:
            pass

        def run_once(self, *, worker_id: str, batch_size: int) -> BootstrapWorkerResult:
            assert (worker_id, batch_size) == ("worker-1", 1)
            initial_fill_started.set()
            assert release_initial_fill.wait(timeout=1)
            return BootstrapWorkerResult(1, 1, 0)

    class RecoveryJobs:
        def recover_expired_leases(self) -> None:
            pass

    arguments = SimpleNamespace(
        worker_id="worker-1", batch_size=1, concurrency=1, poll_seconds=0.01, once=False
    )
    sleep_calls = 0

    def stop_after_second_poll(_: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls == 1:
            assert initial_fill_started.wait(timeout=1)
            return
        assert len(metadata_calls) == 2
        release_initial_fill.set()
        raise StopIteration

    monkeypatch.setenv("PORTFELL_SHARED_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("PORTFELL_DATABASE_URL", "postgresql://example")
    monkeypatch.setattr(
        bootstrap_worker_module,
        "build_parser",
        lambda: SimpleNamespace(parse_args=lambda _: arguments),
    )
    monkeypatch.setattr(
        bootstrap_worker_module, "operations_token_from_environment", lambda: "token"
    )
    monkeypatch.setattr(
        bootstrap_worker_module, "connect", lambda *_args, **_kwargs: connections.pop(0)
    )
    monkeypatch.setattr(
        bootstrap_worker_module,
        "PostgresDurableJobRepository",
        lambda _connection, **_kwargs: RecoveryJobs(),
    )
    monkeypatch.setattr(bootstrap_worker_module, "PostgresSelectionMembers", lambda _: object())
    monkeypatch.setattr(bootstrap_worker_module, "SharedMarketDataStore", lambda _: object())
    monkeypatch.setattr(bootstrap_worker_module, "runtime_eodhd_config", lambda _: object())
    monkeypatch.setattr(bootstrap_worker_module, "EodhdClient", lambda _: object())
    monkeypatch.setattr(bootstrap_worker_module, "eodhd_fetch", lambda _: object())
    monkeypatch.setattr(bootstrap_worker_module, "ProjectBootstrapWorker", InitialFillWorker)
    monkeypatch.setattr(
        bootstrap_worker_module,
        "build_metadata_refresh_worker",
        lambda *_args, **_kwargs: MetadataWorker(),
    )
    monkeypatch.setattr(bootstrap_worker_module.time, "sleep", stop_after_second_poll)

    with pytest.raises(StopIteration):
        bootstrap_worker_module.main([])
