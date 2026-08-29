from __future__ import annotations

from pathlib import Path

import pytest

from portfell.hosted_api_errors import HostedRuntimeError
from portfell.hosted_postgres_runtime import PostgresHostedRuntime
from portfell.market_source.gateway import MarketDataGateway


def test_postgres_runtime_exposes_only_an_injected_market_gateway() -> None:
    gateway = MarketDataGateway(lambda: None, role="portfell", member_of="portfell_app")  # type: ignore[arg-type]

    assert PostgresHostedRuntime(Path("shared"), market_gateway=gateway).market_gateway is gateway


def test_postgres_runtime_fails_closed_without_market_gateway() -> None:
    with pytest.raises(HostedRuntimeError, match="market_source_not_configured"):
        _ = PostgresHostedRuntime(Path("shared")).market_gateway
