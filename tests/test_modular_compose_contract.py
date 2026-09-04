"""PR421 Compose topology contract tests."""

from __future__ import annotations

from pathlib import Path

from portfell.services.process import create_process_app


def test_modular_compose_has_exact_container_set_and_only_gateway_port() -> None:
    compose = Path("compose.modules.yaml").read_text()
    expected = (
        "portfell-gateway",
        "portfell-metadata",
        "portfell-univariate",
        "portfell-bivariate",
        "portfell-multivariate",
        "portfell-postgres",
    )
    assert all(f"container_name: {name}" in compose for name in expected)
    assert compose.count('ports: ["0.0.0.0:${PORTFELL_PORT:-8080}:8000"]') == 1
    assert compose.count('expose: ["8000"]') == 4
    assert "/var/lib/portfell/market-data:ro" in compose


def test_process_entrypoint_rejects_monolith_or_unknown_module() -> None:
    assert create_process_app("metadata").title == "Portfell metadata"
    try:
        create_process_app("api")
    except ValueError as error:
        assert str(error) == "unknown_process_module"
    else:
        raise AssertionError("monolith fallback was accepted")
