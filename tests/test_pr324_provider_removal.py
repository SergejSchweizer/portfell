"""Negative-space checks for PR324's retired provider acquisition surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from portfell.cli import build_parser
from portfell.market_source.errors import MARKET_SOURCE_UNAVAILABLE, MarketSourceError

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_retired_provider_client_and_executable_fetch_modules_are_absent() -> None:
    source = REPOSITORY_ROOT / "src" / "portfell"

    for module in ("http.py", "search.py", "fetch_all_metadata.py", "fetch_all_quotes.py"):
        assert not (source / module).exists()
    assert "EodhdClient" not in "\n".join(
        path.read_text(encoding="utf-8") for path in source.rglob("*.py")
    )


def test_umbrella_cli_does_not_expose_retired_acquisition_commands() -> None:
    parser = build_parser()

    for command in ("search", "fetch-all-metadata", "fetch-all-quotes"):
        with pytest.raises(SystemExit) as error:
            parser.parse_args([command])
        assert error.value.code == 2


def test_transitional_non_acquisition_seam_fails_closed() -> None:
    from portfell.market_source.errors import UnavailableMarketDataClient

    with pytest.raises(MarketSourceError, match=MARKET_SOURCE_UNAVAILABLE):
        UnavailableMarketDataClient().get_json("/anything", {"fmt": "json"})
