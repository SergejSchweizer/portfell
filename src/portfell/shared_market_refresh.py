"""Idempotent, lock-protected refresh orchestration for shared market data."""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

from portfell.config import EodhdConfig
from portfell.hosted_database_connection import connect
from portfell.hosted_postgres_active_inventory import PostgresActiveProjectInventory
from portfell.http import EodhdClient
from portfell.logging import get_logger, log_event, setup_logging
from portfell.shared_market_data import (
    SharedListingKey,
    SharedMarketDataStore,
    inventory_hash,
)
from portfell.table_io import JsonRow

DATASETS = ("quotes", "dividends", "splits")
DEFAULT_CORRECTION_OVERLAP_DAYS = 7
_WRITE_BATCH_SIZE = 128
LOGGER = get_logger(__name__)


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
            if (
                record is not None
                and record.last_business_date is not None
                and date.fromisoformat(record.last_business_date) >= end_date
            ):
                continue
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
    fetch: ProviderFetch,
    end_date: date,
    listings: Iterable[SharedListingKey],
    concurrency: int = 4,
    dry_run: bool = False,
    on_listing_completed: Callable[[SharedListingKey], None] | None = None,
) -> RefreshResult:
    """Refresh each unique listing/dataset once and persist a redacted manifest."""

    if concurrency < 1:
        raise SharedMarketRefreshError("invalid_refresh_concurrency")
    resolved_listings = tuple(listings)
    requests = plan_refresh(store, resolved_listings, end_date=end_date)
    result_hash = inventory_hash(resolved_listings)
    log_event(
        LOGGER,
        logging.INFO,
        module="shared-market-refresh",
        event="refresh_planned",
        fields={
            "concurrency": concurrency,
            "listing_count": len(resolved_listings),
            "requested": len(requests),
            "target_date": end_date.isoformat(),
        },
    )
    if dry_run:
        return RefreshResult(
            result_hash, end_date.isoformat(), len(requests), 0, 0, 0, True, requests
        )
    with _refresh_lock(store.root):
        updated = 0
        unchanged = 0
        errors: list[str] = []
        requests_per_listing = {
            listing: sum(1 for request in requests if request.listing == listing)
            for listing in resolved_listings
        }
        completed_requests_per_listing = dict.fromkeys(requests_per_listing, 0)
        for listing, request_count in requests_per_listing.items():
            if request_count == 0 and on_listing_completed is not None:
                on_listing_completed(listing)

        def mark_request_completed(request: RefreshRequest) -> None:
            completed_requests_per_listing[request.listing] += 1
            if (
                completed_requests_per_listing[request.listing]
                == requests_per_listing[request.listing]
                and on_listing_completed is not None
            ):
                on_listing_completed(request.listing)

        def record_completed_request(request: RefreshRequest, changed: bool) -> None:
            nonlocal updated, unchanged
            if changed:
                updated += 1
            else:
                unchanged += 1
            mark_request_completed(request)

        def publish_batch(
            batch: list[tuple[RefreshRequest, tuple[Mapping[str, Any], ...]]],
        ) -> None:
            if not batch:
                return
            try:
                changed = store.upsert_many(
                    (request.dataset_type, request.listing, rows) for request, rows in batch
                )
            except Exception as error:
                log_event(
                    LOGGER,
                    logging.ERROR,
                    module="shared-market-refresh",
                    event="batch_persist_failed",
                    fields={"batch_size": len(batch), "target_date": end_date.isoformat()},
                    error=error,
                )
                errors.extend("provider_or_storage_failure" for _ in batch)
                for request, _ in batch:
                    mark_request_completed(request)
                return
            for (request, _), item_changed in zip(batch, changed, strict=True):
                record_completed_request(request, item_changed)

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(_fetch_rows, fetch, request): request for request in requests
            }
            batch: list[tuple[RefreshRequest, tuple[Mapping[str, Any], ...]]] = []
            for future in as_completed(futures):
                request = futures[future]
                try:
                    rows = future.result()
                except Exception as error:
                    log_event(
                        LOGGER,
                        logging.ERROR,
                        module="shared-market-refresh",
                        event="provider_request_failed",
                        fields={
                            "code": request.listing.code,
                            "dataset_type": request.dataset_type,
                            "exchange": request.listing.exchange,
                            "isin": request.listing.isin,
                            "start_date": request.start_date or "full_history",
                        },
                        error=error,
                    )
                    errors.append("provider_or_storage_failure")
                    mark_request_completed(request)
                else:
                    batch.append((request, rows))
                    if len(batch) == _WRITE_BATCH_SIZE:
                        publish_batch(batch)
                        batch = []
            publish_batch(batch)
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
        log_event(
            LOGGER,
            logging.INFO if not errors else logging.WARNING,
            module="shared-market-refresh",
            event="refresh_completed",
            fields={
                "failed": len(errors),
                "requested": len(requests),
                "unchanged": unchanged,
                "updated": updated,
            },
        )
        if errors:
            raise SharedMarketRefreshError("shared_market_refresh_partial_failure")
        return result


def _fetch_rows(fetch: ProviderFetch, request: RefreshRequest) -> tuple[Mapping[str, Any], ...]:
    return tuple(fetch(request))


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


def build_parser() -> argparse.ArgumentParser:
    """Build the non-interactive shared market refresh command parser."""

    parser = argparse.ArgumentParser(description="Refresh canonical Portfell shared market data.")
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the operations-credential refresh against the active project inventory."""

    args = build_parser().parse_args(argv)
    setup_logging(debug=os.environ.get("PORTFELL_LOG_LEVEL", "").upper() == "DEBUG")
    root = os.environ.get("PORTFELL_SHARED_DATA_ROOT")
    database_url = os.environ.get("PORTFELL_DATABASE_URL")
    operations_token = operations_token_from_environment()
    if not root or not database_url or (not args.dry_run and not operations_token):
        return 4
    try:
        return _run_postgres_refresh(args, Path(root), database_url, operations_token)
    except SharedMarketRefreshError as error:
        log_event(
            LOGGER,
            logging.ERROR,
            module="shared-market-refresh",
            event="refresh_failed",
            fields={"exit_code": 2 if str(error) == "shared_market_refresh_locked" else 5},
            error=error,
        )
        return 2 if str(error) == "shared_market_refresh_locked" else 5
    except Exception as error:
        log_event(
            LOGGER,
            logging.ERROR,
            module="shared-market-refresh",
            event="refresh_failed",
            fields={"exit_code": 4},
            error=error,
        )
        return 4


def _run_postgres_refresh(
    args: argparse.Namespace, root: Path, database_url: str, operations_token: str
) -> int:
    connection = connect(database_url, autocommit=False)
    try:
        listings = PostgresActiveProjectInventory(connection).listings()
    finally:
        connection.close()
    store = SharedMarketDataStore(root)
    fetch = (
        _empty_fetch
        if args.dry_run
        else eodhd_fetch(EodhdClient(EodhdConfig(api_token=operations_token)))
    )
    result = refresh_shared_market_data(
        store=store,
        listings=listings,
        fetch=fetch,
        end_date=args.end_date,
        concurrency=args.concurrency,
        dry_run=args.dry_run,
    )
    print(json.dumps(result.row(), sort_keys=True))
    return 0


def _empty_fetch(_: RefreshRequest) -> tuple[Mapping[str, Any], ...]:
    return ()


def operations_token_from_environment() -> str:
    path = os.environ.get("PORTFELL_OPERATIONS_EODHD_TOKEN_FILE")
    if path:
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return os.environ.get("PORTFELL_OPERATIONS_EODHD_TOKEN", "").strip()


def eodhd_fetch(client: EodhdClient) -> ProviderFetch:
    endpoints = {"quotes": "eod", "dividends": "div", "splits": "splits"}

    def fetch(request: RefreshRequest) -> Iterable[Mapping[str, Any]]:
        params: dict[str, str] = {"fmt": "json", "to": request.end_date}
        if request.start_date:
            params["from"] = request.start_date
        payload = client.get_json(
            f"/{endpoints[request.dataset_type]}/{request.listing.code}.{request.listing.exchange}",
            params,
        )
        if not isinstance(payload, list):
            raise SharedMarketRefreshError("provider_response_invalid")
        payload_rows = cast(list[object], payload)
        return [
            {**request.listing.as_row(), **dict(cast(Mapping[str, Any], row))}
            for row in payload_rows
            if isinstance(row, Mapping)
        ]

    return fetch


# Backward-compatible test seam; production consumers use ``eodhd_fetch``.
_eodhd_fetch = eodhd_fetch


if __name__ == "__main__":
    raise SystemExit(main())
