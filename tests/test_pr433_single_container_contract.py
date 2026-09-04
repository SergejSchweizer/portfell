from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contracts" / "single-container-modules-v1.md"


def test_single_container_contract_defines_one_application_and_four_internal_modules() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "one Application container" in text
    assert "one PostgreSQL service" in text
    for module, route, prefix in (
        ("Metadata", "/metadata", "/api/metadata"),
        ("Univariate", "/univariate", "/api/univariate"),
        ("Bivariate", "/bivariate", "/api/bivariate"),
        ("Multivariate", "/multivariate", "/api/multivariate"),
    ):
        assert module in text
        assert route in text
        assert prefix in text
    assert "typed IDs, immutable persisted artifacts" in text


def test_supported_compose_shape_is_one_application_plus_postgres() -> None:
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    assert set(compose["services"]) == {"api", "postgres"}
    assert compose["services"]["api"]["container_name"] == "portfell-app"
    assert compose["services"]["api"]["ports"] == ["0.0.0.0:${PORTFELL_PORT:-8080}:8000"]


def test_contract_has_ordered_toc_and_forbids_process_split() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    sections = (
        "## Purpose",
        "## Runtime topology",
        "## Internal module boundaries",
        "## Persistence and hand-off",
        "## Forbidden topology",
        "## Acceptance gate",
    )
    assert [text.index(section) for section in sections] == sorted(
        text.index(section) for section in sections
    )
    assert "a second Application container" in text
    assert "sibling implementation import" in text
