from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

import portfell.shared_market_refresh as refresh
from portfell.hosted_api_state import HostedApiState, ProjectRecord, SelectionRecord
from portfell.shared_market_data import SharedListingKey, SharedMarketDataStore
from portfell.shared_market_refresh import (
    RefreshResult,
    SharedMarketRefreshError,
    plan_refresh,
    refresh_shared_market_data,
)


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


def test_refresh_rejects_invalid_settings_and_persists_partial_failure(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)
    with pytest.raises(SharedMarketRefreshError, match="invalid_correction_overlap"):
        plan_refresh(store, (), end_date=date(2026, 1, 1), correction_overlap_days=-1)
    with pytest.raises(SharedMarketRefreshError, match="invalid_refresh_concurrency"):
        refresh_shared_market_data(
            store=store, state=_state(), fetch=_fetch, end_date=date(2026, 1, 1), concurrency=0
        )

    def failing_fetch(request):  # type: ignore[no-untyped-def]
        if request.dataset_type == "splits":
            raise RuntimeError("provider unavailable")
        return _fetch(request)

    with pytest.raises(SharedMarketRefreshError, match="partial_failure"):
        refresh_shared_market_data(
            store=store, state=_state(), fetch=failing_fetch, end_date=date(2026, 1, 1)
        )
    manifest = (store.root / "refresh-runs" / "2026-01-01.json").read_text(encoding="utf-8")
    assert '"failed": 1' in manifest


def test_refresh_lock_and_cli_exit_codes(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)
    state = _state()
    monkeypatch.delenv("PORTFELL_SHARED_DATA_ROOT", raising=False)
    monkeypatch.delenv("PORTFELL_EODHD_KEK_FILE", raising=False)
    assert refresh.main([]) == 4

    monkeypatch.setenv("PORTFELL_SHARED_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("PORTFELL_EODHD_KEK_FILE", str(tmp_path / "kek"))
    monkeypatch.setattr(
        refresh,
        "create_persistent_local_workspace_state",
        lambda *_args, **_kwargs: state,
    )
    monkeypatch.setattr(refresh, "load_key_encryption_key", lambda *_args, **_kwargs: object())
    state.shared_market_data_store = store
    assert refresh.main(["--dry-run", "--end-date", "2026-01-01"]) == 0
    assert '"dry_run": true' in capsys.readouterr().out

    monkeypatch.setenv("PORTFELL_OPERATIONS_EODHD_TOKEN", "operations-secret")
    state.shared_market_data_store = None
    assert refresh.main([]) == 6
    monkeypatch.setattr(
        refresh,
        "create_persistent_local_workspace_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()),
    )
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
    monkeypatch.setenv("PORTFELL_EODHD_KEK_FILE", str(tmp_path / "kek"))
    monkeypatch.delenv("PORTFELL_OPERATIONS_EODHD_TOKEN", raising=False)
    monkeypatch.setattr(
        refresh,
        "create_persistent_local_workspace_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not plan")),
    )

    assert refresh.main(["--end-date", "2026-01-01"]) == 4


def test_refresh_cli_uses_operations_credential_for_a_non_dry_run(
    tmp_path, monkeypatch, capsys
) -> None:  # type: ignore[no-untyped-def]
    state = _state()
    state.shared_market_data_store = SharedMarketDataStore(tmp_path)
    monkeypatch.setenv("PORTFELL_SHARED_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("PORTFELL_EODHD_KEK_FILE", str(tmp_path / "kek"))
    monkeypatch.setenv("PORTFELL_OPERATIONS_EODHD_TOKEN", "operations-secret")
    monkeypatch.setattr(
        refresh,
        "create_persistent_local_workspace_state",
        lambda *_args, **_kwargs: state,
    )
    monkeypatch.setattr(refresh, "load_key_encryption_key", lambda *_args, **_kwargs: object())
    received_tokens: list[str] = []
    monkeypatch.setattr(
        refresh,
        "EodhdClient",
        lambda config: received_tokens.append(config.api_token) or object(),
    )
    monkeypatch.setattr(
        refresh,
        "refresh_shared_market_data",
        lambda **_kwargs: RefreshResult("inventory", "2026-01-01", 0, 0, 0, 0, False, ()),
    )

    assert refresh.main(["--end-date", "2026-01-01"]) == 0
    assert received_tokens == ["operations-secret"]
    assert '"dry_run": false' in capsys.readouterr().out
