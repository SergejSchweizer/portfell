"""Idempotent, lock-protected refresh orchestration for shared market data."""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Callable, Generator, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from portfell.shared_market_data import (
    SharedListingKey,
    SharedMarketDataStore,
    active_project_inventory,
    inventory_hash,
)
from portfell.table_io import JsonRow

DATASETS = ("quotes", "dividends", "splits")
DEFAULT_CORRECTION_OVERLAP_DAYS = 7


class SharedMarketRefreshError(RuntimeError):
    """Raised for refresh preflight, lock, provider, or storage failures."""


@dataclass(frozen=True)
class RefreshRequest:
    """One listing/dataset provider request, full or bounded delta."""

    dataset_type: str
    listing: SharedListingKey
    start_date: str | None
    end_date: str


@dataclass(frozen=True)
class RefreshResult:
    """Stable, redacted result summary for a refresh run."""

    inventory_hash: str
    target_date: str
    requested: int
    updated: int
    unchanged: int
    failed: int
    dry_run: bool
    requests: tuple[RefreshRequest, ...]
    errors: tuple[str, ...] = ()

    def row(self) -> JsonRow:
        return {
            "inventory_hash": self.inventory_hash,
            "target_date": self.target_date,
            "requested": self.requested,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "failed": self.failed,
            "dry_run": self.dry_run,
            "requests": [
                {
                    "dataset_type": item.dataset_type,
                    **item.listing.as_row(),
                    "start_date": item.start_date,
                    "end_date": item.end_date,
                }
                for item in self.requests
            ],
            "errors": list(self.errors),
        }


ProviderFetch = Callable[[RefreshRequest], Iterable[Mapping[str, Any]]]


def plan_refresh(
    store: SharedMarketDataStore,
    listings: Iterable[SharedListingKey],
    *,
    end_date: date,
    correction_overlap_days: int = DEFAULT_CORRECTION_OVERLAP_DAYS,
) -> tuple[RefreshRequest, ...]:
    """Create deterministic full/backfill or bounded-overlap delta requests."""

    if correction_overlap_days < 0:
        raise SharedMarketRefreshError("invalid_correction_overlap")
    coverage = {(record.dataset_type, record.listing): record for record in store.coverage()}
    planned: list[RefreshRequest] = []
    for listing in sorted(set(listings)):
        for dataset_type in DATASETS:
            record = coverage.get((dataset_type, listing))
            start = None
            if record is not None and record.last_business_date is not None:
                start = (
                    date.fromisoformat(record.last_business_date)
                    - timedelta(days=correction_overlap_days)
                ).isoformat()
            planned.append(RefreshRequest(dataset_type, listing, start, end_date.isoformat()))
    return tuple(planned)


def refresh_shared_market_data(
    *,
    store: SharedMarketDataStore,
    state: object,
    fetch: ProviderFetch,
    end_date: date,
    concurrency: int = 4,
    dry_run: bool = False,
) -> RefreshResult:
    """Refresh each unique listing/dataset once and persist a redacted manifest."""

    if concurrency < 1:
        raise SharedMarketRefreshError("invalid_refresh_concurrency")
    listings = active_project_inventory(state)  # type: ignore[arg-type]
    requests = plan_refresh(store, listings, end_date=end_date)
    result_hash = inventory_hash(listings)
    if dry_run:
        return RefreshResult(
            result_hash, end_date.isoformat(), len(requests), 0, 0, 0, True, requests
        )
    with _refresh_lock(store.root):
        updated = 0
        unchanged = 0
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(_refresh_one, store, fetch, request): request
                for request in requests
            }
            for future in as_completed(futures):
                try:
                    changed = future.result()
                except Exception:
                    errors.append("provider_or_storage_failure")
                else:
                    if changed:
                        updated += 1
                    else:
                        unchanged += 1
        result = RefreshResult(
            result_hash,
            end_date.isoformat(),
            len(requests),
            updated,
            unchanged,
            len(errors),
            False,
            requests,
            tuple(sorted(errors)),
        )
        _write_manifest(store.root, result)
        if errors:
            raise SharedMarketRefreshError("shared_market_refresh_partial_failure")
        return result


def _refresh_one(
    store: SharedMarketDataStore, fetch: ProviderFetch, request: RefreshRequest
) -> bool:
    before = store.coverage()
    before_hash = next(
        (
            item.content_hash
            for item in before
            if item.dataset_type == request.dataset_type and item.listing == request.listing
        ),
        None,
    )
    record = store.upsert(request.dataset_type, request.listing, fetch(request))
    return record.content_hash != before_hash


@contextmanager
def _refresh_lock(root: Path) -> Generator[None]:
    path = root / ".refresh.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise SharedMarketRefreshError("shared_market_refresh_locked") from error
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()}\n")
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_manifest(root: Path, result: RefreshResult) -> None:
    path = root / "refresh-runs" / f"{result.target_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.row(), sort_keys=True) + "\n", encoding="utf-8")
