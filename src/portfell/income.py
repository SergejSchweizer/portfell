"""Jurisdiction-neutral gross historical distribution evidence.

This boundary describes observed distributions only. It deliberately has no
tax, broker-cost, sustainable-income, or synthetic-NAV calculation path.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from math import sqrt
from statistics import median
from typing import Any

from portfell.contract_versioning import ContractVersion, stable_contract_id
from portfell.multivariate_inputs import MultivariateListingKey

INCOME_CONTRACT = ContractVersion("multivariate.income", 1)


@dataclass(frozen=True)
class IncomePolicy:
    version: ContractVersion = INCOME_CONTRACT
    minimum_observed_months: int = 12
    lower_percentile: float = 0.1
    trailing_days: int = 365

    def to_row(self) -> dict[str, object]:
        return {
            "version": self.version.qualified_name,
            "minimum_observed_months": self.minimum_observed_months,
            "lower_percentile": self.lower_percentile,
            "trailing_days": self.trailing_days,
        }


DEFAULT_INCOME_POLICY = IncomePolicy()


@dataclass(frozen=True)
class DistributionEvent:
    listing: MultivariateListingKey
    event_date: str
    amount: float
    currency: str
    source_id: str
    used_payment_date_fallback: bool


@dataclass(frozen=True)
class IncomeEvidence:
    income_id: str
    listing: MultivariateListingKey
    currency: str | None
    event_count: int
    observed_month_count: int
    gross_ttm_distribution_amount: float | None
    gross_ttm_distribution_yield: float | None
    mean_observed_monthly_distribution: float | None
    median_observed_monthly_distribution: float | None
    lower_percentile_monthly_distribution: float | None
    coefficient_of_variation: float | None
    cut_count: int | None
    largest_cut: float | None
    longest_falling_sequence: int | None
    nav_erosion: None
    availability_reasons: tuple[str, ...]
    warnings: tuple[str, ...]


def normalize_distribution_events(
    rows: Sequence[Mapping[str, Any]], *, listing: MultivariateListingKey
) -> tuple[DistributionEvent, ...]:
    """Normalize explicit corrections/deletions and de-duplicate source events."""
    latest: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if MultivariateListingKey.from_row(row) != listing:
            continue
        source_id = str(row.get("event_id", row.get("id", row.get("source_id", ""))))
        if not source_id:
            source_id = stable_contract_id("income_event_source", dict(row))
        latest[source_id] = row
    events: list[DistributionEvent] = []
    for source_id, row in sorted(latest.items()):
        if bool(row.get("deleted", False)):
            continue
        raw_date = str(row.get("payment_date") or row.get("date") or row.get("ex_date") or "")
        if not raw_date:
            continue
        amount = float(row.get("amount", row.get("value", row.get("unadjustedValue", 0.0))) or 0.0)
        if amount < 0:
            continue
        currency = str(row.get("currency", ""))
        events.append(
            DistributionEvent(
                listing=listing,
                event_date=raw_date,
                amount=amount,
                currency=currency,
                source_id=source_id,
                used_payment_date_fallback=not bool(row.get("payment_date")),
            )
        )
    return tuple(sorted(events, key=lambda event: (event.event_date, event.source_id)))


def build_income_evidence(
    *,
    listing: MultivariateListingKey,
    events: Sequence[DistributionEvent],
    period_end: str,
    denominator_price: float | None,
    policy: IncomePolicy = DEFAULT_INCOME_POLICY,
) -> IncomeEvidence:
    """Summarise gross observed monthly distributions, never inferred zeros."""
    currencies = {event.currency for event in events if event.currency}
    reasons: list[str] = []
    warnings: list[str] = []
    if len(currencies) > 1:
        reasons.append("currency_mismatch")
    if not events:
        reasons.append("no_distribution_events")
    buckets: dict[str, float] = defaultdict(float)
    for event in events:
        buckets[event.event_date[:7]] += event.amount
    observed = tuple(value for _, value in sorted(buckets.items()))
    if len(observed) < policy.minimum_observed_months:
        reasons.append("insufficient_observed_months")
    if any(event.used_payment_date_fallback for event in events):
        warnings.append("payment_date_fallback_used")
    end = date.fromisoformat(period_end)
    trailing = sum(
        event.amount
        for event in events
        if 0 <= (end - date.fromisoformat(event.event_date)).days <= policy.trailing_days
    )
    price = denominator_price if denominator_price and denominator_price > 0 else None
    if price is None:
        reasons.append("dated_price_denominator_unavailable")
    available = not reasons
    monthly = sorted(observed)
    lower_index = (
        max(0, min(len(monthly) - 1, int((len(monthly) - 1) * policy.lower_percentile)))
        if monthly
        else 0
    )
    average = sum(observed) / len(observed) if observed else None
    variance = (
        sum((value - average) ** 2 for value in observed) / len(observed)
        if average is not None and observed
        else None
    )
    coefficient = (
        sqrt(variance) / average if variance is not None and average and average > 0 else None
    )
    cuts = [
        previous - current
        for previous, current in zip(observed, observed[1:], strict=False)
        if current < previous
    ]
    identity = stable_contract_id(
        "income_evidence",
        {
            "contract": INCOME_CONTRACT.qualified_name,
            "listing": listing.as_tuple(),
            "events": [(event.event_date, event.amount, event.source_id) for event in events],
            "period_end": period_end,
            "price": price,
            "policy": policy.to_row(),
        },
    )
    return IncomeEvidence(
        income_id=identity,
        listing=listing,
        currency=next(iter(currencies), None),
        event_count=len(events),
        observed_month_count=len(observed),
        gross_ttm_distribution_amount=trailing if available else None,
        gross_ttm_distribution_yield=(trailing / price) if available and price else None,
        mean_observed_monthly_distribution=average if available else None,
        median_observed_monthly_distribution=median(observed) if available else None,
        lower_percentile_monthly_distribution=monthly[lower_index]
        if available and monthly
        else None,
        coefficient_of_variation=coefficient if available else None,
        cut_count=len(cuts) if available else None,
        largest_cut=max(cuts) if available and cuts else None,
        longest_falling_sequence=_longest_falling_sequence(observed) if available else None,
        nav_erosion=None,
        availability_reasons=tuple(sorted(set(reasons))),
        warnings=tuple(sorted(set(warnings))),
    )


def _longest_falling_sequence(values: Sequence[float]) -> int:
    best = current = 0
    for previous, value in zip(values, values[1:], strict=False):
        current = current + 1 if value < previous else 0
        best = max(best, current)
    return best
