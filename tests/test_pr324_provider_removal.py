"""Negative-space checks for PR324's retired provider acquisition surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from portfell.market_source.errors import MARKET_SOURCE_UNAVAILABLE, MarketSourceError

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_retired_provider_client_and_executable_fetch_modules_are_absent() -> None:
    source = REPOSITORY_ROOT / "src" / "portfell"

    for module in ("http.py", "search.py", "fetch_all_metadata.py", "fetch_all_quotes.py"):
        assert not (source / module).exists()
    assert "EodhdClient" not in "\n".join(
        path.read_text(encoding="utf-8") for path in source.rglob("*.py")
    )


def test_retired_acquisition_cli_is_not_an_executable_surface() -> None:
    """The legacy umbrella CLI was deleted with the provider acquisition flow."""

    source = REPOSITORY_ROOT / "src" / "portfell"
    pyproject = (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert not (source / "cli.py").exists()
    assert "portfell.cli:main" not in pyproject


def test_transitional_non_acquisition_seam_fails_closed() -> None:
    from portfell.market_source.errors import UnavailableMarketDataClient

    with pytest.raises(MarketSourceError, match=MARKET_SOURCE_UNAVAILABLE):
        UnavailableMarketDataClient().get_json("/anything", {"fmt": "json"})
