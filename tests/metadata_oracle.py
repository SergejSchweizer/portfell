"""Independent deterministic oracle for Metadata module acceptance tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetadataListing:
    isin: str
    exchange: str
    instrument_type: str
    country: str
    currency: str


FIXTURE_LISTINGS = (
    MetadataListing("DE000TEST01", "XETRA", "ETF", "DE", "EUR"),
    MetadataListing("DE000TEST01", "XETRA", "ETF", "DE", "EUR"),
    MetadataListing("DE000TEST02", "XETRA", "ETF", "DE", "EUR"),
    MetadataListing("FR000TEST03", "PARIS", "ETF", "FR", "EUR"),
)


def expected_unique_isins(**filters: str | None) -> int:
    rows = [
        row
        for row in FIXTURE_LISTINGS
        if all(value is None or getattr(row, key) == value for key, value in filters.items())
    ]
    return len({row.isin for row in rows})


def expected_option_counts(**filters: str | None) -> dict[str, dict[str, int]]:
    rows = [
        row
        for row in FIXTURE_LISTINGS
        if all(value is None or getattr(row, key) == value for key, value in filters.items())
    ]
    return {
        key: {
            value: len({row.isin for row in rows if getattr(row, key) == value})
            for value in sorted({getattr(row, key) for row in rows})
        }
        for key in ("exchange", "instrument_type", "country", "currency")
    }
