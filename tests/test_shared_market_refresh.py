from __future__ import annotations

from datetime import date

from portfell.hosted_api_state import HostedApiState, ProjectRecord, SelectionRecord
from portfell.shared_market_data import SharedMarketDataStore
from portfell.shared_market_refresh import plan_refresh, refresh_shared_market_data


def _state() -> HostedApiState:
    return HostedApiState(
        projects_by_id={"p": ProjectRecord("p", "user", "P")},
        selections_by_id={"s": SelectionRecord("s", "user", "p", "S", ("IE1:XETRA:ABC",))},
    )


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
        store=store, state=_state(), fetch=_fetch, end_date=date(2026, 1, 10), concurrency=2
    )
    second = refresh_shared_market_data(
        store=store, state=_state(), fetch=_fetch, end_date=date(2026, 1, 10), concurrency=2
    )
    assert first.requested == 3 and first.updated == 3
    assert second.requested == 3 and second.unchanged == 3
    assert len(store.coverage()) == 3
    assert (store.root / "refresh-runs" / "2026-01-10.json").is_file()


def test_delta_plan_uses_bounded_correction_overlap_and_dry_run_writes_nothing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)
    dry = refresh_shared_market_data(
        store=store, state=_state(), fetch=_fetch, end_date=date(2026, 1, 10), dry_run=True
    )
    assert dry.dry_run and not store.root.exists()
    refreshed = refresh_shared_market_data(
        store=store, state=_state(), fetch=_fetch, end_date=date(2026, 1, 10)
    )
    assert all(item.start_date is None for item in refreshed.requests)
    planned = plan_refresh(store, [refreshed.requests[0].listing], end_date=date(2026, 1, 11))
    assert all(item.start_date == "2026-01-03" for item in planned)
