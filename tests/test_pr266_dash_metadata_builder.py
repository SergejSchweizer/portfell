from __future__ import annotations

from pathlib import Path

import pytest

from portfell.dash_ui.callbacks.metadata_builder.commands import command_key
from portfell.dash_ui.viewmodels.metadata_builder.model import MetadataBuilderView


def _view() -> MetadataBuilderView:
    return MetadataBuilderView(
        fetch_status="complete",
        fetch_active=False,
        fetch_percent=100.0,
        exchange_options=(("Xetra", "XETRA"),),
        instrument_type_options=(("ETF", "ETF"),),
        country_options=(("Germany", "DE"),),
        currency_options=(("EUR", "EUR"),),
        can_create_project=True,
        listing_count=12,
        unique_isin_count=11,
        history_label="Observed history: 2020-01-02 to 2026-08-19",
        downstream_states=(
            ("univariate", "not_run", "not_started"),
            ("bivariate", "blocked", "univariate_required"),
            ("multivariate", "blocked", "bivariate_required"),
        ),
    )


def test_pr266_command_identity_is_deterministic_for_duplicate_callbacks() -> None:
    first = command_key(
        command="create_project",
        project_slug=None,
        payload={"exchange": "XETRA", "currency": "EUR"},
    )
    second = command_key(
        command="create_project",
        project_slug=None,
        payload={"currency": "EUR", "exchange": "XETRA"},
    )
    assert first == second
    assert len(first) == 64


def test_pr266_metadata_view_preserves_listing_and_unique_isin_counts() -> None:
    view = _view()
    assert view.listing_count == 12
    assert view.unique_isin_count == 11
    assert view.fetch_percent == 100.0
    assert [state for _, state, _ in view.downstream_states] == [
        "not_run",
        "blocked",
        "blocked",
    ]


def test_pr266_non_available_downstream_state_requires_reason() -> None:
    with pytest.raises(ValueError, match="requires a reason"):
        MetadataBuilderView(
            fetch_status="idle",
            fetch_active=False,
            fetch_percent=None,
            exchange_options=(),
            instrument_type_options=(),
            country_options=(),
            currency_options=(),
            can_create_project=False,
            listing_count=0,
            unique_isin_count=0,
            history_label="History unavailable",
            downstream_states=(("univariate", "blocked", None),),
        )


def test_pr266_layout_source_contains_exactly_the_five_builder_criteria() -> None:
    source = Path("src/portfell/dash_ui/pages/metadata_builder/layout.py").read_text(
        encoding="utf-8"
    )
    for label in ("Exchange", "Instrument type", "Country", "Currency", "Name contains"):
        assert source.count(f'"{label}"') == 1
    assert "provider_key" not in source
    assert "EODHD" not in source


def test_pr266_layout_smoke_when_dash_dependency_is_available() -> None:
    pytest.importorskip("dash")
    from portfell.dash_ui.pages.metadata_builder.layout import build_metadata_layout

    layout = build_metadata_layout(_view())
    assert getattr(layout, "id", None) == "metadata-page"
