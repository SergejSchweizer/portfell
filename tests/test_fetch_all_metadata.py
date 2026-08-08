from collections.abc import Mapping
from pathlib import Path

import pytest

from portfell.fetch_all_metadata import fetch_all_metadata, write_all_metadata
from portfell.http import EodhdHttpError
from portfell.paths import LakePaths
from portfell.table_io import read_json, read_rows
from portfell.workflows import run_fetch_all_metadata_workflow


class FakeClient:
    def __init__(self) -> None:
        self.requested_paths: list[str] = []

    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | float] | None = None,
    ) -> object:
        self.requested_paths.append(path)
        if path == "/exchanges-list/":
            return [{"Code": "XETRA"}, {"Code": "US"}]
        if path == "/exchange-symbol-list/XETRA":
            return [
                {
                    "Code": "AAA",
                    "Exchange": "XETRA",
                    "Name": "Example UCITS ETF",
                    "Type": "ETF",
                    "Country": "DE",
                    "Currency": "EUR",
                    "Isin": "IE1",
                }
            ]
        if path == "/exchange-symbol-list/US":
            return [{"Code": "NOISIN", "Exchange": "US", "Name": "No ISIN"}]
        raise AssertionError(path)


def test_fetch_all_metadata_enumerates_exchanges_and_keeps_isin_rows() -> None:
    progress: list[tuple[int, int, int]] = []
    result = fetch_all_metadata(FakeClient(), on_progress=lambda *values: progress.append(values))

    assert result.requested_exchanges == ("US", "XETRA")
    assert result.skipped_exchanges == ()
    assert progress == [(0, 2, 0), (1, 2, 0), (2, 2, 0)]
    assert list(result.rows) == [
        {
            "isin": "IE1",
            "exchange": "XETRA",
            "code": "AAA",
            "name": "Example UCITS ETF",
            "instrument_type": "ETF",
            "country": "DE",
            "currency": "EUR",
            "source_exchange": "XETRA",
            "fetched_at": result.rows[0]["fetched_at"],
        }
    ]


def test_fetch_all_metadata_discards_null_like_isin_values() -> None:
    class NullIsinClient:
        def get_json(
            self, path: str, params: Mapping[str, str | int | float] | None = None
        ) -> object:
            del params
            if path == "/exchange-symbol-list/XETRA":
                return [
                    {"Code": "AAA", "Exchange": "XETRA", "Isin": None},
                    {"Code": "BBB", "Exchange": "XETRA", "Isin": "None"},
                    {"Code": "CCC", "Exchange": "XETRA", "Isin": "IE1"},
                ]
            raise AssertionError(path)

    result = fetch_all_metadata(NullIsinClient(), exchange_codes=("XETRA",))

    assert [(row["isin"], row["code"]) for row in result.rows] == [("IE1", "CCC")]


class ForbiddenExchangeClient(FakeClient):
    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | float] | None = None,
    ) -> object:
        if path == "/exchanges-list/":
            return [{"Code": "MONEY"}, {"Code": "XETRA"}]
        if path == "/exchange-symbol-list/MONEY":
            raise EodhdHttpError("forbidden", status_code=403)
        return super().get_json(path, params)


def test_fetch_all_metadata_skips_forbidden_auto_enumerated_exchanges() -> None:
    result = fetch_all_metadata(ForbiddenExchangeClient())

    assert result.requested_exchanges == ("MONEY", "XETRA")
    assert result.skipped_exchanges == ("MONEY",)
    assert len(result.rows) == 1


def test_fetch_all_metadata_fails_for_explicit_forbidden_exchange() -> None:
    with pytest.raises(EodhdHttpError, match="forbidden"):
        fetch_all_metadata(ForbiddenExchangeClient(), exchange_codes=("MONEY",))


def test_write_all_metadata_persists_rows_and_manifest(tmp_path: Path) -> None:
    paths = LakePaths(root=tmp_path / "lake")
    rows = [
        {
            "isin": "IE1",
            "exchange": "XETRA",
            "code": "AAA",
            "name": "Example UCITS ETF",
            "instrument_type": "ETF",
            "country": "DE",
            "currency": "EUR",
            "source_exchange": "XETRA",
            "fetched_at": "2026-01-01T00:00:00+00:00",
        }
    ]

    written = write_all_metadata(paths, rows)

    assert written == rows
    assert read_rows(paths.all_isins()) == rows
    manifest = read_json(paths.all_isins_manifest())
    assert manifest["dataset"] == "all_isins"
    assert manifest["path"] == str(paths.all_isins())
    assert manifest["row_count"] == 1
    assert manifest["updated_at"].endswith("+00:00")


def test_run_fetch_all_metadata_workflow_persists_reference_dataset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = LakePaths(root=tmp_path / "lake")
    monkeypatch.setattr("portfell.workflows.load_eodhd_config", lambda: object())
    monkeypatch.setattr("portfell.workflows.EodhdClient", lambda _config: FakeClient())

    summary = run_fetch_all_metadata_workflow(root=paths.root)

    assert summary["all_isins_rows"] == 1
    assert summary["exchange_count"] == 1
    assert summary["path"] == str(paths.all_isins())
    assert summary["requested_exchange_count"] == 2
    assert summary["skipped_exchange_count"] == 0
    assert summary["skipped_exchanges"] == []
    assert read_rows(paths.all_isins())[0]["isin"] == "IE1"


def test_run_fetch_all_metadata_workflow_preserves_persisted_rows_and_fetches_only_delta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = LakePaths(root=tmp_path / "lake")
    client = FakeClient()
    monkeypatch.setattr("portfell.workflows.load_eodhd_config", lambda: object())
    monkeypatch.setattr("portfell.workflows.EodhdClient", lambda _config: client)

    run_fetch_all_metadata_workflow(root=paths.root)
    client.requested_paths.clear()

    summary = run_fetch_all_metadata_workflow(root=paths.root)

    assert client.requested_paths == ["/exchanges-list/"]
    assert summary["all_isins_rows"] == 1
    assert summary["requested_exchange_count"] == 0
    assert read_rows(paths.all_isins())[0]["isin"] == "IE1"
    assert read_json(paths.all_isins_manifest())["completed_exchanges"] == ["US", "XETRA"]
