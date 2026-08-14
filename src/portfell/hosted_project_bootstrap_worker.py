"""Worker-owned execution of exact project initial-fill jobs."""

from __future__ import annotations

import argparse
import logging
import os
import time
from collections.abc import Callable, Generator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Protocol

from portfell.config import runtime_eodhd_config
from portfell.durable_job_repository import ClaimedJob, PostgresDurableJobRepository
from portfell.hosted_catalog import set_authenticated_user_sql
from portfell.hosted_database_connection import connect
from portfell.hosted_metadata_refresh_worker import build_metadata_refresh_worker
from portfell.hosted_navigation_reconciler import PostgresNavigationReconciler
from portfell.hosted_postgres_repository_bundle import PostgresHostedRepositoryBundle
from portfell.hosted_postgres_runtime import PostgresHostedRuntime
from portfell.hosted_postgres_workflow import PostgresWorkflowReader
from portfell.hosted_project_bootstrap_repository import PostgresProjectBootstrapRepository
from portfell.hosted_project_workflow_projection_repository import (
    PostgresProjectWorkflowProjection,
)
from portfell.hosted_project_workflow_projector import PostgresProjectWorkflowProjector
from portfell.hosted_status_event_repository import PostgresStatusEventRepository
from portfell.hosted_worker_capacity import (
    resolve_worker_concurrency,
    worker_concurrency_from_environment,
)
from portfell.http import EodhdClient
from portfell.logging import get_logger, log_event, setup_logging
from portfell.shared_market_data import SharedListingKey, SharedMarketDataStore
from portfell.shared_market_refresh import (
    ProviderFetch,
    RefreshResult,
    SharedMarketRefreshError,
    eodhd_fetch,
    operations_token_from_environment,
    refresh_shared_market_data,
)

LOGGER = get_logger(__name__)


class BootstrapJobQueue(Protocol):
    def claim(self, *, worker_id: str, batch_size: int) -> tuple[ClaimedJob, ...]: ...

    def update_progress(
        self, *, job_id: str, lease_token: str, completed_units: int, total_units: int
    ) -> None: ...

    def set_initial_fill_failed_listing_count(
        self, *, job_id: str, user_id: str, failed_listing_count: int
    ) -> None: ...

    def heartbeat(self, *, job_id: str, lease_token: str) -> None: ...

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
        heartbeat_interval_seconds: float = 60.0,
    ) -> None:
        self._jobs = jobs
        self._members_for_selection = members_for_selection
        self._store = store
        self._fetch = fetch
        self._end_date = end_date
        self._concurrency = concurrency
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds_must_be_positive")
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._job_writes = Lock()

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
        log_event(
            LOGGER,
            logging.INFO,
            module="project-bootstrap-worker",
            event="job_started",
            fields={"job_id": job.job_id, "job_kind": job.job_kind, "project_id": job.project_id},
        )
        try:
            members = self._members_for_selection(job.user_id, job.input_ref)
            listings = tuple(SharedListingKey.from_member_id(member) for member in members)
            if not listings:
                raise ValueError("bootstrap_members_required")
            self._update_progress(job=job, completed_units=0, total_units=len(listings))
            completed_listings = 0

            def report_listing_completed(_: SharedListingKey) -> None:
                nonlocal completed_listings
                completed_listings += 1
                self._update_progress(
                    job=job, completed_units=completed_listings, total_units=len(listings)
                )

            with self._lease_heartbeat(job):
                result = refresh_shared_market_data(
                    store=self._store,
                    listings=listings,
                    fetch=self._fetch,
                    end_date=self._end_date,
                    concurrency=self._concurrency,
                    on_listing_completed=report_listing_completed,
                )
            self._complete(job, result, len(listings))
        except Exception as error:
            failed_listing_count = len(
                error.failed_listings if isinstance(error, SharedMarketRefreshError) else ()
            )
            self._jobs.set_initial_fill_failed_listing_count(
                job_id=job.job_id,
                user_id=job.user_id,
                failed_listing_count=failed_listing_count,
            )
            log_event(
                LOGGER,
                logging.ERROR,
                module="project-bootstrap-worker",
                event="job_failed",
                fields={
                    "job_id": job.job_id,
                    "job_kind": job.job_kind,
                    "project_id": job.project_id,
                    "selection_id": job.input_ref,
                },
                error=error,
            )
            self._jobs.complete(
                job_id=job.job_id,
                lease_token=job.lease_token,
                status="failed",
                terminal_code="initial_fill_failed",
            )
            return False
        return True

    @contextmanager
    def _lease_heartbeat(self, job: ClaimedJob) -> Generator[None]:
        stopped = Event()

        def renew_lease() -> None:
            while not stopped.wait(self._heartbeat_interval_seconds):
                try:
                    with self._job_writes:
                        self._jobs.heartbeat(job_id=job.job_id, lease_token=job.lease_token)
                except Exception as error:
                    log_event(
                        LOGGER,
                        logging.ERROR,
                        module="project-bootstrap-worker",
                        event="job_heartbeat_failed",
                        fields={"job_id": job.job_id, "job_kind": job.job_kind},
                        error=error,
                    )
                    return

        heartbeat = Thread(target=renew_lease, name=f"portfell-heartbeat-{job.job_id}", daemon=True)
        heartbeat.start()
        try:
            yield
        finally:
            stopped.set()
            heartbeat.join()

    def _update_progress(self, *, job: ClaimedJob, completed_units: int, total_units: int) -> None:
        with self._job_writes:
            self._jobs.update_progress(
                job_id=job.job_id,
                lease_token=job.lease_token,
                completed_units=completed_units,
                total_units=total_units,
            )

    def _complete(self, job: ClaimedJob, result: RefreshResult, listing_count: int) -> None:
        self._update_progress(job=job, completed_units=listing_count, total_units=listing_count)
        self._jobs.complete(
            job_id=job.job_id,
            lease_token=job.lease_token,
            status="partial" if result.failed else "succeeded",
            terminal_code=None if not result.failed else "initial_fill_partial",
        )
        log_event(
            LOGGER,
            logging.INFO if not result.failed else logging.WARNING,
            module="project-bootstrap-worker",
            event="job_completed",
            fields={
                "failed_requests": result.failed,
                "job_id": job.job_id,
                "job_kind": job.job_kind,
                "listing_count": listing_count,
                "status": "partial" if result.failed else "succeeded",
                "updated_requests": result.updated,
            },
        )


def build_parser() -> argparse.ArgumentParser:
    """Build the non-interactive worker command parser."""

    parser = argparse.ArgumentParser(description="Run Portfell project initial-fill worker jobs.")
    parser.add_argument("--worker-id", default=f"bootstrap-worker-{os.getpid()}")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run worker-owned initial fills and metadata refreshes with the operations credential."""

    args = build_parser().parse_args(argv)
    setup_logging(debug=os.environ.get("PORTFELL_LOG_LEVEL", "").upper() == "DEBUG")
    root = os.environ.get("PORTFELL_SHARED_DATA_ROOT")
    database_url = os.environ.get("PORTFELL_DATABASE_URL")
    token = operations_token_from_environment()
    try:
        configured_concurrency = (
            args.concurrency
            if args.concurrency is not None
            else worker_concurrency_from_environment(os.environ)
        )
        concurrency = resolve_worker_concurrency(
            os.process_cpu_count(), configured_concurrency=configured_concurrency
        )
    except ValueError:
        return 4
    if not root or not database_url or not token or args.batch_size < 1 or args.poll_seconds <= 0:
        return 4
    log_event(
        LOGGER,
        logging.INFO,
        module="project-bootstrap-worker",
        event="worker_capacity_configured",
        fields={"concurrency": concurrency, "workload": "bootstrap_and_metadata"},
    )
    # Repositories explicitly delimit each claim/update with ``transaction()``.
    # Autocommit keeps those worker transactions short-lived instead of retaining
    # an implicit outer transaction for the lifetime of the polling process.
    bootstrap_connection = connect(database_url, autocommit=True)
    metadata_connection = connect(database_url, autocommit=True)
    try:
        navigation_reconciler = PostgresNavigationReconciler(bootstrap_connection)
        workflow_repositories = PostgresHostedRepositoryBundle.from_connection(
            bootstrap_connection,
            navigation_refresher=navigation_reconciler.reconcile,
        )
        workflow_projector = PostgresProjectWorkflowProjector(
            PostgresWorkflowReader(
                selections=workflow_repositories.selections,
                bootstrap=PostgresProjectBootstrapRepository(bootstrap_connection),
                metadata_rows=PostgresHostedRuntime(Path(root)).all_isins_rows,
            ),
            PostgresProjectWorkflowProjection(bootstrap_connection),
            PostgresStatusEventRepository(bootstrap_connection),
        )
        bootstrap_jobs = PostgresDurableJobRepository(
            bootstrap_connection,
            navigation_refresher=navigation_reconciler.reconcile,
            workflow_refresher=workflow_projector.reconcile,
            status_events=PostgresStatusEventRepository(bootstrap_connection),
        )
        recovery_jobs = PostgresDurableJobRepository(
            metadata_connection,
            navigation_refresher=PostgresNavigationReconciler(metadata_connection).reconcile,
            status_events=PostgresStatusEventRepository(metadata_connection),
        )
        worker = ProjectBootstrapWorker(
            jobs=bootstrap_jobs,
            members_for_selection=PostgresSelectionMembers(bootstrap_connection),
            store=SharedMarketDataStore(Path(root)),
            fetch=eodhd_fetch(EodhdClient(runtime_eodhd_config(token))),
            end_date=date.today(),
            concurrency=concurrency,
        )
        metadata_worker = build_metadata_refresh_worker(
            metadata_connection,
            shared_data_root=Path(root),
            operations_token=token,
            concurrency=concurrency,
        )
        with ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="project-initial-fill"
        ) as executor:
            initial_fill: Future[BootstrapWorkerResult] | None = None
            last_status_event_prune = 0.0
            while True:
                recovery_jobs.recover_expired_leases()
                if time.monotonic() - last_status_event_prune >= 60 and hasattr(
                    metadata_connection, "execute"
                ):
                    PostgresStatusEventRepository(metadata_connection).prune_expired()
                    last_status_event_prune = time.monotonic()
                metadata_result = metadata_worker.run_once()
                if initial_fill is None:
                    initial_fill = executor.submit(
                        worker.run_once, worker_id=args.worker_id, batch_size=args.batch_size
                    )
                if args.once:
                    result = initial_fill.result()
                    metadata_succeeded = not metadata_result.claimed or metadata_result.succeeded
                    return 0 if result.failed_count == 0 and metadata_succeeded else 5
                if initial_fill.done():
                    result = initial_fill.result()
                    initial_fill = None
                else:
                    result = BootstrapWorkerResult(0, 0, 0)
                if result.claimed_count == 0 and not metadata_result.claimed:
                    time.sleep(args.poll_seconds)
    finally:
        bootstrap_connection.close()
        metadata_connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
