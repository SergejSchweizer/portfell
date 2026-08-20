"""Typed Metadata Builder view model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetadataBuilderView:
    fetch_status: str
    fetch_active: bool
    fetch_percent: float | None
    exchange_options: tuple[tuple[str, str], ...]
    instrument_type_options: tuple[tuple[str, str], ...]
    country_options: tuple[tuple[str, str], ...]
    currency_options: tuple[tuple[str, str], ...]
    can_create_project: bool
    listing_count: int
    unique_isin_count: int
    history_label: str
    downstream_states: tuple[tuple[str, str, str | None], ...] = ()

    def __post_init__(self) -> None:
        if self.listing_count < 0 or self.unique_isin_count < 0:
            raise ValueError("universe counts cannot be negative")
        if self.unique_isin_count > self.listing_count:
            raise ValueError("unique ISIN count cannot exceed listing count")
        if self.fetch_percent is not None and not 0 <= self.fetch_percent <= 100:
            raise ValueError("fetch_percent must be within [0, 100]")
        allowed_states = {"available", "not_run", "blocked", "unavailable"}
        for stage, state, reason in self.downstream_states:
            if not stage or state not in allowed_states:
                raise ValueError("invalid downstream history state")
            if state != "available" and not reason:
                raise ValueError("non-available downstream state requires a reason")
