"""Worker-owned execution of exact project initial-fill jobs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from portfell.durable_job_repository import ClaimedJob
from portfell.shared_market_data import SharedListingKey, SharedMarketDataStore
from portfell.shared_market_refresh import ProviderFetch, RefreshResult, refresh_shared_market_data


class BootstrapJobQueue(Protocol):
    def claim(self, *, worker_id: str, batch_size: int) -> tuple[ClaimedJob, ...]: ...

    def update_progress(
        self, *, job_id: str, lease_token: str, completed_units: int, total_units: int
    ) -> None: ...

    def complete(
        self, *, job_id: str, lease_token: str, status: str, terminal_code: str | None = None
    ) -> None: ...


SelectionMembers = Callable[[str, str], tuple[str, ...]]


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
