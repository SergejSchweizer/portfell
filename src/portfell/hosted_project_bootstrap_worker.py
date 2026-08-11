"""Worker-owned execution of exact project initial-fill jobs."""

from __future__ import annotations

import argparse
import os
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from portfell.config import EodhdConfig
from portfell.durable_job_repository import ClaimedJob, PostgresDurableJobRepository
from portfell.hosted_catalog import set_authenticated_user_sql
from portfell.hosted_database_connection import connect
from portfell.http import EodhdClient
from portfell.shared_market_data import SharedListingKey, SharedMarketDataStore
from portfell.shared_market_refresh import (
    ProviderFetch,
    RefreshResult,
    _eodhd_fetch,
    _operations_token,
    refresh_shared_market_data,
)


class BootstrapJobQueue(Protocol):
    def claim(self, *, worker_id: str, batch_size: int) -> tuple[ClaimedJob, ...]: ...

    def update_progress(
        self, *, job_id: str, lease_token: str, completed_units: int, total_units: int
    ) -> None: ...

    def complete(
        self, *, job_id: str, lease_token: str, status: str, terminal_code: str | None = None
    ) -> None: ...


SelectionMembers = Callable[[str, str], tuple[str, ...]]


class SelectionCursor(Protocol):
    def fetchall(self) -> list[tuple[object, ...]]: ...


class SelectionConnection(Protocol):
    def transaction(self) -> AbstractContextManager[object]: ...

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> SelectionCursor: ...


class PostgresSelectionMembers:
    """Read one RLS-owned immutable member set for a claimed worker job."""

    def __init__(self, connection: SelectionConnection) -> None:
        self._connection = connection

    def __call__(self, user_id: str, selection_id: str) -> tuple[str, ...]:
        with self._connection.transaction():
            self._connection.execute(*set_authenticated_user_sql(user_id))
            rows = self._connection.execute(
                """
select isin, exchange, code
from portfell_app.project_selection_members
where selection_version_id = %s::uuid
order by isin, exchange, code
""",
                (selection_id,),
            ).fetchall()
        if any(
            len(row) != 3 or not all(isinstance(value, str) and value for value in row)
            for row in rows
        ):
            raise ValueError("bootstrap_members_projection_invalid")
        return tuple(f"{row[0]}:{row[1]}:{row[2]}" for row in rows)


@dataclass(frozen=True)
class BootstrapWorkerResult:
    """Redacted worker result that can be reported in operational metrics."""

    claimed_count: int
    succeeded_count: int
    failed_count: int


class ProjectBootstrapWorker:
    """Consume only exact-selection initial-fill jobs using the operations provider role."""

    def __init__(
        self,
        *,
        jobs: BootstrapJobQueue,
        members_for_selection: SelectionMembers,
        store: SharedMarketDataStore,
        fetch: ProviderFetch,
        end_date: date,
        concurrency: int,
    ) -> None:
        self._jobs = jobs
        self._members_for_selection = members_for_selection
        self._store = store
        self._fetch = fetch
        self._end_date = end_date
        self._concurrency = concurrency

    def run_once(self, *, worker_id: str, batch_size: int = 1) -> BootstrapWorkerResult:
        """Claim and execute a bounded batch without using active-project inventory."""

        claimed = self._jobs.claim(worker_id=worker_id, batch_size=batch_size)
        succeeded = 0
        failed = 0
        for job in claimed:
            if job.job_kind != "project_initial_fill":
                continue
            if self._execute(job):
                succeeded += 1
            else:
                failed += 1
        return BootstrapWorkerResult(len(claimed), succeeded, failed)

    def _execute(self, job: ClaimedJob) -> bool:
        try:
            members = self._members_for_selection(job.user_id, job.input_ref)
            listings = tuple(SharedListingKey.from_member_id(member) for member in members)
            if not listings:
                raise ValueError("bootstrap_members_required")
            self._jobs.update_progress(
                job_id=job.job_id,
                lease_token=job.lease_token,
                completed_units=0,
                total_units=len(listings),
            )
            result = refresh_shared_market_data(
                store=self._store,
                listings=listings,
                fetch=self._fetch,
                end_date=self._end_date,
                concurrency=self._concurrency,
            )
            self._complete(job, result, len(listings))
        except Exception:
            self._jobs.complete(
                job_id=job.job_id,
                lease_token=job.lease_token,
                status="failed",
                terminal_code="initial_fill_failed",
            )
            return False
        return True

    def _complete(self, job: ClaimedJob, result: RefreshResult, listing_count: int) -> None:
        self._jobs.update_progress(
            job_id=job.job_id,
            lease_token=job.lease_token,
            completed_units=listing_count,
            total_units=listing_count,
        )
        self._jobs.complete(
            job_id=job.job_id,
            lease_token=job.lease_token,
            status="partial" if result.failed else "succeeded",
            terminal_code=None if not result.failed else "initial_fill_partial",
        )


def build_parser() -> argparse.ArgumentParser:
    """Build the non-interactive worker command parser."""

    parser = argparse.ArgumentParser(description="Run Portfell project initial-fill worker jobs.")
    parser.add_argument("--worker-id", default=f"bootstrap-worker-{os.getpid()}")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=max(1, os.process_cpu_count() or 1))
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run worker-owned initial fills using only the operations market credential."""

    args = build_parser().parse_args(argv)
    root = os.environ.get("PORTFELL_SHARED_DATA_ROOT")
    database_url = os.environ.get("PORTFELL_DATABASE_URL")
    token = _operations_token()
    if (
        not root
        or not database_url
        or not token
        or args.batch_size < 1
        or args.concurrency < 1
        or args.poll_seconds <= 0
    ):
        return 4
    connection = connect(database_url, autocommit=False)
    try:
        worker = ProjectBootstrapWorker(
            jobs=PostgresDurableJobRepository(connection),
            members_for_selection=PostgresSelectionMembers(connection),
            store=SharedMarketDataStore(Path(root)),
            fetch=_eodhd_fetch(EodhdClient(EodhdConfig(api_token=token))),
            end_date=date.today(),
            concurrency=args.concurrency,
        )
        while True:
            result = worker.run_once(worker_id=args.worker_id, batch_size=args.batch_size)
            if args.once:
                return 0 if result.failed_count == 0 else 5
            if result.claimed_count == 0:
                time.sleep(args.poll_seconds)
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
