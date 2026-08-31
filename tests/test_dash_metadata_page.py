from __future__ import annotations

from dataclasses import dataclass

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

    def create_metadata_universe(self, **filters: object) -> Universe:
        self.created = dict(filters)
        return Universe()


def test_page_data_keeps_full_identity_and_exact_counts() -> None:
    model = metadata_page_data(Service())
    rows = model["rows"]
    assert isinstance(rows, tuple)
    assert [(row["isin"], row["exchange"], row["code"]) for row in rows] == [
        ("DE000A", "XETRA", "AAA"),
        ("DE000A", "XETRA", "AAB"),
    ]
    assert model["active_count"] == 2
    assert model["filtered_count"] == 2
    assert model["selected_count"] == 2
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
        "Build the active Xetra instrument universe.",
        "Reset filters",
        "Create universe",
        "Active listings",
        "Filtered listings",
        "Selected listings",
        "Universe version",
        "Xetra Listings",
        "Universe & History",
        "Continue to Univariate",
        "DE000A",
        "AAA",
        "AAB",
    ):
        assert text in rendered
    assert "provider" not in rendered.lower()
    assert "download" not in rendered.lower()
