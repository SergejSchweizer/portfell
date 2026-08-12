from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

import portfell.shared_market_refresh as refresh
from portfell.shared_market_data import SharedListingKey, SharedMarketDataStore
from portfell.shared_market_refresh import (
    RefreshResult,
    SharedMarketRefreshError,
    plan_refresh,
    refresh_shared_market_data,
)

_LISTINGS = (SharedListingKey("eodhd", "XETRA", "ABC", "IE1"),)


def _fetch(request):  # type: ignore[no-untyped-def]
    row = {**request.listing.as_row(), "date": request.end_date}
    if request.dataset_type == "quotes":
        row["adjusted_close"] = 10.0
    elif request.dataset_type == "dividends":
        row["event_id"] = f"event-{request.end_date}"
    else:
        row["split_factor"] = 1.0
    return [row]


def test_first_refresh_backfills_once_and_second_refresh_is_idempotent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)
    first = refresh_shared_market_data(
        store=store, listings=_LISTINGS, fetch=_fetch, end_date=date(2026, 1, 10), concurrency=2
    )
    second = refresh_shared_market_data(
        store=store, listings=_LISTINGS, fetch=_fetch, end_date=date(2026, 1, 10), concurrency=2
    )
    assert first.requested == 3 and first.updated == 3
    assert second.requested == 0 and second.unchanged == 0
    assert len(store.coverage()) == 3
    assert (store.root / "refresh-runs" / "2026-01-10.json").is_file()


def test_delta_plan_uses_bounded_correction_overlap_and_dry_run_writes_nothing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)
    dry = refresh_shared_market_data(
        store=store, listings=_LISTINGS, fetch=_fetch, end_date=date(2026, 1, 10), dry_run=True
    )
    assert dry.dry_run and not store.root.exists()
    refreshed = refresh_shared_market_data(
        store=store, listings=_LISTINGS, fetch=_fetch, end_date=date(2026, 1, 10)
    )
    assert all(item.start_date is None for item in refreshed.requests)
    planned = plan_refresh(store, [refreshed.requests[0].listing], end_date=date(2026, 1, 11))
    assert all(item.start_date == "2026-01-03" for item in planned)


def test_delta_plan_skips_fully_covered_data_and_backfills_only_new_listings(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)
    covered = SharedListingKey("eodhd", "XETRA", "ABC", "IE1")
    fresh = SharedListingKey("eodhd", "XETRA", "XYZ", "IE2")
    for dataset in ("quotes", "dividends", "splits"):
        row = {**covered.as_row(), "date": "2026-01-10"}
        if dataset == "quotes":
            row["adjusted_close"] = 10.0
        elif dataset == "dividends":
            row["event_id"] = "event"
        else:
            row["split_factor"] = 1.0
        store.upsert(dataset, covered, [row])

    requests = plan_refresh(store, [covered, fresh], end_date=date(2026, 1, 10))

    assert [(item.dataset_type, item.listing.isin, item.start_date) for item in requests] == [
        ("quotes", "IE2", None),
        ("dividends", "IE2", None),
        ("splits", "IE2", None),
    ]


def test_refresh_skips_empty_dividend_and_split_responses_after_they_are_checked(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)

    def fetch(request):  # type: ignore[no-untyped-def]
        return _fetch(request) if request.dataset_type == "quotes" else ()

    first = refresh_shared_market_data(
        store=store, listings=_LISTINGS, fetch=fetch, end_date=date(2026, 1, 10)
    )
    second = refresh_shared_market_data(
        store=store, listings=_LISTINGS, fetch=fetch, end_date=date(2026, 1, 10)
    )
    coverage = {record.dataset_type: record for record in store.coverage()}

    assert first.requested == 3
    assert second.requested == 0
    assert coverage["dividends"].last_business_date is None
    assert coverage["dividends"].last_checked_date == "2026-01-10"
    assert coverage["splits"].last_checked_date == "2026-01-10"


def test_batch_publish_reads_and_replaces_coverage_once(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)
    reads = 0
    original_read_catalog = store._read_catalog

    def count_catalog_reads():  # type: ignore[no-untyped-def]
        nonlocal reads
        reads += 1
        return original_read_catalog()

    monkeypatch.setattr(store, "_read_catalog", count_catalog_reads)
    listings = tuple(
        SharedListingKey("eodhd", "XETRA", f"A{index}", f"IE{index}") for index in range(3)
    )
    changed = store.upsert_many(
        (
            "quotes",
            listing,
            _fetch(
                SimpleNamespace(
                    listing=listing,
                    dataset_type="quotes",
                    end_date="2026-01-10",
                )
            ),
            "2026-01-10",
        )
        for listing in listings
    )

    assert changed == (True, True, True)
    assert reads == 1
    assert len(store.coverage()) == 3


def test_refresh_accepts_worker_owned_inventory_without_workspace_state(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = refresh_shared_market_data(
        store=SharedMarketDataStore(tmp_path),
        listings=(SharedListingKey("eodhd", "XETRA", "ABC", "IE1"),),
        fetch=_fetch,
        end_date=date(2026, 1, 10),
    )

    assert result.requested == 3


def test_refresh_rejects_invalid_settings_and_persists_partial_failure(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)
    with pytest.raises(SharedMarketRefreshError, match="invalid_correction_overlap"):
        plan_refresh(store, (), end_date=date(2026, 1, 1), correction_overlap_days=-1)
    with pytest.raises(SharedMarketRefreshError, match="invalid_refresh_concurrency"):
        refresh_shared_market_data(
            store=store, listings=_LISTINGS, fetch=_fetch, end_date=date(2026, 1, 1), concurrency=0
        )

    def failing_fetch(request):  # type: ignore[no-untyped-def]
        if request.dataset_type == "splits":
            raise RuntimeError("provider unavailable")
        return _fetch(request)

    completed: list[SharedListingKey] = []
    with pytest.raises(SharedMarketRefreshError, match="partial_failure"):
        refresh_shared_market_data(
            store=store,
            listings=_LISTINGS,
            fetch=failing_fetch,
            end_date=date(2026, 1, 1),
            on_listing_completed=completed.append,
        )
    manifest = (store.root / "refresh-runs" / "2026-01-01.json").read_text(encoding="utf-8")
    assert '"failed": 1' in manifest
    assert completed == list(_LISTINGS)


def test_refresh_persists_successful_fetch_before_interruption(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)

    def interrupted_fetch(request):  # type: ignore[no-untyped-def]
        if request.dataset_type == "dividends":
            raise KeyboardInterrupt
        return _fetch(request)

    with pytest.raises(KeyboardInterrupt):
        refresh_shared_market_data(
            store=store,
            listings=_LISTINGS,
            fetch=interrupted_fetch,
            end_date=date(2026, 1, 1),
            concurrency=1,
        )

    coverage = {record.dataset_type: record for record in store.coverage()}
    assert coverage["quotes"].last_checked_date == "2026-01-01"


def test_refresh_lock_and_cli_exit_codes(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    _ = capsys
    monkeypatch.delenv("PORTFELL_SHARED_DATA_ROOT", raising=False)
    monkeypatch.delenv("PORTFELL_DATABASE_URL", raising=False)
    assert refresh.main([]) == 4

    monkeypatch.setenv("PORTFELL_SHARED_DATA_ROOT", str(tmp_path))
    assert refresh.main(["--dry-run", "--end-date", "2026-01-01"]) == 4
    assert refresh.main([]) == 4


def test_eodhd_fetch_scopes_requests_and_rejects_invalid_payloads() -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    class Client:
        def get_json(self, path: str, params: dict[str, str]) -> object:
            calls.append((path, params))
            return [{"date": "2026-01-01", "adjusted_close": 10.0}]

    request = refresh.RefreshRequest(
        "quotes", SharedListingKey("eodhd", "XETRA", "ABC", "IE1"), "2025-12-25", "2026-01-01"
    )
    rows = list(refresh._eodhd_fetch(Client())(request))
    assert rows[0]["isin"] == "IE1"
    assert calls == [("/eod/ABC.XETRA", {"fmt": "json", "to": "2026-01-01", "from": "2025-12-25"})]

    invalid = SimpleNamespace(get_json=lambda *_args, **_kwargs: {"invalid": True})
    with pytest.raises(SharedMarketRefreshError, match="provider_response_invalid"):
        list(refresh._eodhd_fetch(invalid)(request))


def test_refresh_cli_requires_operations_credential_before_planning(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PORTFELL_SHARED_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("PORTFELL_DATABASE_URL", "postgresql://worker@postgres/portfell")
    monkeypatch.delenv("PORTFELL_OPERATIONS_EODHD_TOKEN", raising=False)

    assert refresh.main(["--end-date", "2026-01-01"]) == 4


def test_refresh_cli_reads_postgres_active_inventory(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    class Connection:
        def close(self) -> None:
            return None

    class Inventory:
        def __init__(self, _connection: Connection) -> None:
            pass

        def listings(self) -> tuple[SharedListingKey, ...]:
            return (SharedListingKey("eodhd", "XETRA", "ABC", "IE1"),)

    monkeypatch.setenv("PORTFELL_SHARED_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("PORTFELL_DATABASE_URL", "postgresql://worker@postgres/portfell")
    monkeypatch.setenv("PORTFELL_OPERATIONS_EODHD_TOKEN", "operations-secret")
    monkeypatch.setattr(refresh, "connect", lambda *_args, **_kwargs: Connection())
    monkeypatch.setattr(refresh, "PostgresActiveProjectInventory", Inventory)
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        refresh,
        "refresh_shared_market_data",
        lambda **kwargs: (
            seen.update(kwargs) or RefreshResult("inventory", "2026-01-01", 0, 0, 0, 0, False, ())
        ),
    )

    assert refresh.main(["--end-date", "2026-01-01"]) == 0
    assert seen["listings"] == (SharedListingKey("eodhd", "XETRA", "ABC", "IE1"),)
    assert '"dry_run": false' in capsys.readouterr().out
