from __future__ import annotations

from pathlib import Path

CONTRACT = Path(__file__).parents[1] / "docs" / "contracts" / "independent-modules-v1.md"


def test_independent_module_contract_freezes_all_four_modules_and_handoffs() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    for module, route, prefix, output in (
        ("Metadata", "/metadata", "/api/metadata", "metadata_universe_id"),
        ("Univariate", "/univariate", "/api/univariate", "univariate_selection_id"),
        ("Bivariate", "/bivariate", "/api/bivariate", "bivariate_run_id"),
        ("Multivariate", "/multivariate", "/api/multivariate", "multivariate_run_id"),
    ):
        assert module in text
        assert route in text
        assert prefix in text
        assert output in text
    assert "Metadata -> Univariate -> Bivariate -> Multivariate" in text


def test_independent_module_contract_forbids_unsafe_handoffs() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    for forbidden in (
        "sibling implementation import",
        "direct sibling Python call",
        "cross-module database write",
        "unpublished or unverified data-share artifact",
        "complete analytical data in a REST hand-off",
        "generic `/api/runs` endpoint",
    ):
        assert forbidden in text


def test_contract_has_required_navigation_sections() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    sections = (
        "## Purpose",
        "## Runtime topology",
        "## Module ownership",
        "## PostgreSQL hand-off",
        "## Shared data share",
        "## Allowed dependencies",
        "## Forbidden dependencies",
        "## Gateway boundary",
        "## Compatibility and migration",
    )
    positions = [text.index(section) for section in sections]
    assert positions == sorted(positions)
