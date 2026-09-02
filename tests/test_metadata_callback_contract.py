from __future__ import annotations

from typing import Any, cast

from portfell.dash_app.app import create_dash_app
from portfell.dash_app.pages.metadata import metadata_page_data


def test_metadata_filter_callback_has_all_four_inputs() -> None:
    app = create_dash_app(services=object())
    callbacks = cast(dict[str, dict[str, Any]], cast(Any, app).callback_map)
    callback = next(
        value
        for key, value in callbacks.items()
        if key.startswith("pf-browser-state.data@")
        and {item["id"] for item in value["inputs"]}
        == {
            "metadata-filter-exchange",
            "metadata-filter-instrument-type",
            "metadata-filter-country",
            "metadata-filter-currency",
        }
    )
    assert callback["state"] == [{"id": "pf-browser-state", "property": "data"}]


def test_metadata_model_counts_unique_isins_for_every_dependent_region() -> None:
    class Service:
        def metadata_options(self) -> dict[str, object]:
            return {"active_listing_count": 99}

        def active_listings(self, **filters: object) -> tuple[dict[str, object], ...]:
            del filters
            def row(isin: str) -> dict[str, object]:
                return {
                    "isin": isin,
                    "exchange": "XETRA",
                    "instrument_type": "ETF",
                    "country": "DE",
                    "currency": "EUR",
                }

            return (
                row("A"),
                row("A"),
                row("B"),
            )

        def metadata_history(self) -> tuple[dict[str, object], ...]:
            return ()

        def workflow_state(self) -> dict[str, object]:
            return {}

    model = metadata_page_data(Service(), filters={"exchange": "XETRA"})
    assert model["active_count"] == 2
    assert model["selected_count"] == 2
    rows = cast(tuple[dict[str, object], ...], model["rows"])
    assert [row["isin"] for row in rows] == ["A", "B"]
    options = cast(dict[str, object], model["options"])
    assert cast(list[dict[str, object]], options["exchange"])[0]["label"] == "XETRA (2)"
