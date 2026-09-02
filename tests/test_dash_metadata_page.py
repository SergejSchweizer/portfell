from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from portfell.dash_app.pages.metadata import build_page, create_universe, metadata_page_data


@dataclass(frozen=True)
class Universe:
    universe_id: str = "universe-1"
    version: int = 3


class Service:
    created: dict[str, object] | None = None

    def metadata_options(self) -> dict[str, object]:
        return {
            "exchange": ["XETRA"],
            "instrument_type": ["ETF"],
            "country": ["DE"],
            "currency": ["EUR"],
            "active_listing_count": 2,
        }

    def active_listings(self, **filters: object) -> tuple[dict[str, object], ...]:
        del filters
        return (
            {
                "isin": "DE000A",
                "exchange": "XETRA",
                "code": "AAA",
                "name": "A",
                "instrument_type": "ETF",
                "country": "DE",
                "currency": "EUR",
            },
            {
                "isin": "DE000A",
                "exchange": "XETRA",
                "code": "AAB",
                "name": "A second listing",
                "instrument_type": "ETF",
                "country": "DE",
                "currency": "EUR",
            },
        )

    def metadata_history(self) -> tuple[dict[str, object], ...]:
        return ()

    def workflow_state(self) -> dict[str, object]:
        return {
            "metadata_universe": {
                "universe_id": "universe-1",
                "version": 3,
                "created_at": "2026-08-30T00:00:00Z",
                "source_snapshot_id": "market_source_snapshot_123456",
                "member_count": 2,
            }
        }

    def create_universe_and_start_univariate(self, **filters: object) -> Universe:
        self.created = dict(filters)
        return Universe()


def test_page_data_keeps_full_identity_and_exact_counts() -> None:
    model = metadata_page_data(Service())
    rows = cast(tuple[dict[str, object], ...], model["rows"])
    assert [(row["isin"], row["exchange"], row["code"]) for row in rows] == [
        ("DE000A", "XETRA", "AAA"),
        ("DE000A", "XETRA", "AAB"),
    ]
    assert model["active_count"] == 2
    assert model["filtered_count"] == 2
    assert model["selected_count"] == 2
    assert model["preview_count"] == 2
    assert model["universe_version"] == 3
    assert model["ready"] is True


def test_create_universe_is_an_explicit_action() -> None:
    service = Service()
    result = create_universe(service, {"exchange": "XETRA", "instrument_type": "ETF"})
    assert result == Universe()
    assert service.created == {
        "exchange": "XETRA",
        "instrument_type": "ETF",
        "country": None,
        "currency": None,
    }


def test_layout_has_frozen_metadata_contract_without_provider_action() -> None:
    rendered = str(build_page(Service()).to_plotly_json())
    for text in (
        "Metadata",
            "Define the starting selection for the analysis funnel.",
        "Active listings",
            "Selected listings",
        "Instrument Type Distribution",
        "Country Distribution",
        "Currency Distribution",
        "XETRA",
        "ETF",
        "DE",
        "EUR",
    ):
        assert text in rendered
    assert "provider" not in rendered.lower()
    assert "download" not in rendered.lower()


def test_page_data_bounds_only_the_non_authoritative_listing_preview() -> None:
    class LargeService(Service):
        def active_listings(self, **filters: object) -> tuple[dict[str, object], ...]:
            del filters
            return tuple(
                {
                    "isin": f"DE{index:010d}",
                    "exchange": "XETRA",
                    "code": f"ETF{index}",
                    "name": f"ETF {index}",
                    "instrument_type": "ETF",
                    "country": "DE",
                    "currency": "EUR",
                }
                for index in range(101)
            )

    model = metadata_page_data(LargeService())

    assert model["filtered_count"] == 101
    assert model["selected_count"] == 101
    assert model["preview_count"] == 100
    assert len(cast(tuple[dict[str, object], ...], model["rows"])) == 100
    rendered = str(build_page(LargeService()).to_plotly_json())
    assert "Instrument Type Distribution" in rendered
    assert "Country Distribution" in rendered
    assert "Currency Distribution" in rendered
    assert "ETF" in rendered
