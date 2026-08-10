"""Idempotent, lock-protected refresh orchestration for shared market data."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

from portfell.config import EodhdConfig
from portfell.hosted_api import create_persistent_local_workspace_state
from portfell.hosted_api_state import HostedApiState
from portfell.hosted_credentials import load_key_encryption_key
from portfell.http import EodhdClient
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
    state: HostedApiState,
    fetch: ProviderFetch,
    end_date: date,
    concurrency: int = 4,
    dry_run: bool = False,
) -> RefreshResult:
    """Refresh each unique listing/dataset once and persist a redacted manifest."""

    if concurrency < 1:
        raise SharedMarketRefreshError("invalid_refresh_concurrency")
    listings = active_project_inventory(state)
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


def build_parser() -> argparse.ArgumentParser:
    """Build the non-interactive shared market refresh command parser."""

    parser = argparse.ArgumentParser(description="Refresh canonical Portfell shared market data.")
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the refresh using the encrypted local-workspace credential only in-process."""

    args = build_parser().parse_args(argv)
    root = os.environ.get("PORTFELL_SHARED_DATA_ROOT")
    key_file = os.environ.get("PORTFELL_EODHD_KEK_FILE")
    operations_token = _operations_token()
    if not root or not key_file or (not args.dry_run and not operations_token):
        return 4
    try:
        state = create_persistent_local_workspace_state(
            Path(root),
            key_encryption_key=load_key_encryption_key(
                Path(key_file), version=os.environ.get("PORTFELL_EODHD_KEK_VERSION", "local-v1")
            ),
        )
        store = state.shared_market_data_store
        if store is None:
            return 6
        if args.dry_run:
            result = refresh_shared_market_data(
                store=store,
                state=state,
                fetch=lambda _: (),
                end_date=args.end_date,
                concurrency=args.concurrency,
                dry_run=True,
            )
        else:
            client = EodhdClient(EodhdConfig(api_token=operations_token))
            result = refresh_shared_market_data(
                store=store,
                state=state,
                fetch=_eodhd_fetch(client),
                end_date=args.end_date,
                concurrency=args.concurrency,
            )
    except SharedMarketRefreshError as error:
        return 2 if str(error) == "shared_market_refresh_locked" else 5
    except Exception:
        return 4
    print(json.dumps(result.row(), sort_keys=True))
    return 0


def _operations_token() -> str:
    path = os.environ.get("PORTFELL_OPERATIONS_EODHD_TOKEN_FILE")
    if path:
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return os.environ.get("PORTFELL_OPERATIONS_EODHD_TOKEN", "").strip()


def _eodhd_fetch(client: EodhdClient) -> ProviderFetch:
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


if __name__ == "__main__":
    raise SystemExit(main())
