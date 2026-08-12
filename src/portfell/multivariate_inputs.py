"""Immutable, scoped inputs for Multivariate Statistics.

This module is deliberately a contract boundary.  It accepts only records
that its caller has already authorised and pinned; it neither reads a
``current`` selection nor starts any Metadata, Univariate, or Bivariate work.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from portfell.contract_versioning import ContractVersion, stable_contract_id

ListingKey = tuple[str, str, str]

INPUT_SNAPSHOT_CONTRACT = ContractVersion("multivariate.input_snapshot", 1)
MONTHLY_DISTRIBUTION_ETF_POLICY = ContractVersion("multivariate.monthly_etf_policy", 2)

REASON_NON_ETF = "non_etf"
REASON_NOT_MONTHLY = "distribution_not_monthly"
REASON_DUPLICATE_LISTING_KEY = "duplicate_listing_key"
REASON_MISSING_QUOTE_ARTIFACT = "missing_quote_artifact"
REASON_MISSING_DIVIDEND_ARTIFACT = "missing_dividend_artifact"
REASON_MISSING_BIVARIATE_DEPENDENCY = "missing_bivariate_dependency"
REASON_BIVARIATE_NOT_COMPLETE = "bivariate_not_complete"
REASON_MEMBERSHIP_MISMATCH = "membership_mismatch"
REASON_CALENDAR_MISMATCH = "calendar_mismatch"
REASON_INSUFFICIENT_COMMON_HISTORY = "insufficient_common_history"
REASON_FEWER_THAN_TWO_LISTINGS = "fewer_than_two_eligible_listings"
REASON_STALE_UPSTREAM = "stale_upstream_dependency"


@dataclass(frozen=True, order=True)
class MultivariateListingKey:
    """The complete identity of one tradable listing; an ISIN alone is not enough."""

    isin: str
    exchange: str
    code: str

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> MultivariateListingKey:
        return cls(str(row.get("isin", "")), str(row.get("exchange", "")), str(row.get("code", "")))

    def as_tuple(self) -> ListingKey:
        return (self.isin, self.exchange, self.code)


@dataclass(frozen=True)
class MonthlyDistributionEtfPolicy:
    """Explicit and serialisable eligibility policy for the first portfolio universe."""

    version: ContractVersion = MONTHLY_DISTRIBUTION_ETF_POLICY
    required_instrument_type: str = "ETF"
    required_distribution_frequency: str = "monthly"
    minimum_listing_count: int = 2
    minimum_common_daily_return_observations: int = 100
    require_production_eligible_quotes: bool = True

    def __post_init__(self) -> None:
        if self.minimum_listing_count < 2:
            raise ValueError("minimum_listing_count must be at least two")
        if self.minimum_common_daily_return_observations < 2:
            raise ValueError("minimum_common_daily_return_observations must be at least two")

    def to_row(self) -> dict[str, object]:
        observations = self.minimum_common_daily_return_observations
        return {
            "version": self.version.qualified_name,
            "required_instrument_type": self.required_instrument_type,
            "required_distribution_frequency": self.required_distribution_frequency,
            "minimum_listing_count": self.minimum_listing_count,
            "minimum_common_daily_return_observations": observations,
            "require_production_eligible_quotes": self.require_production_eligible_quotes,
        }


DEFAULT_MONTHLY_DISTRIBUTION_ETF_POLICY = MonthlyDistributionEtfPolicy()


@dataclass(frozen=True)
class MultivariateInputDependencies:
    """The exact authorised closure from which a snapshot may be constructed."""

    project_id: str
    project_snapshot_id: str
    metadata_selection_id: str
    univariate_run_id: str
    univariate_selection_id: str
    bivariate_run_id: str | None
    bivariate_status: str | None
    bivariate_listing_keys: tuple[MultivariateListingKey, ...]
    aligned_calendar_id: str | None
    bivariate_aligned_calendar_id: str | None
    date_start: str | None
    date_end: str | None
    observation_count: int
    quote_artifact_ids: Mapping[MultivariateListingKey, str]
    dividend_artifact_ids: Mapping[MultivariateListingKey, str]
    upstream_stale: bool = False


@dataclass(frozen=True)
class EligibilityResult:
    """One listing's auditable decision under the monthly ETF policy."""

    listing: MultivariateListingKey
    eligible: bool
    reasons: tuple[str, ...]

    def to_row(self) -> dict[str, object]:
        return {
            "isin": self.listing.isin,
            "exchange": self.listing.exchange,
            "code": self.listing.code,
            "eligible": self.eligible,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class MultivariateInputSnapshot:
    """Versioned immutable project input for all later Multivariate artifacts."""

    snapshot_id: str
    contract_version: ContractVersion
    project_id: str
    project_snapshot_id: str
    metadata_selection_id: str
    univariate_run_id: str
    univariate_selection_id: str
    bivariate_run_id: str
    listing_keys: tuple[MultivariateListingKey, ...]
    quote_artifact_ids: tuple[tuple[MultivariateListingKey, str], ...]
    dividend_artifact_ids: tuple[tuple[MultivariateListingKey, str], ...]
    aligned_calendar_id: str
    date_start: str
    date_end: str
    observation_count: int
    policy: MonthlyDistributionEtfPolicy
    dependency_hash: str
    eligibility: tuple[EligibilityResult, ...]
    availability_reasons: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return not self.availability_reasons

    def to_row(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "contract_version": self.contract_version.qualified_name,
            "project_id": self.project_id,
            "project_snapshot_id": self.project_snapshot_id,
            "metadata_selection_id": self.metadata_selection_id,
            "univariate_run_id": self.univariate_run_id,
            "univariate_selection_id": self.univariate_selection_id,
            "bivariate_run_id": self.bivariate_run_id,
            "listing_keys": [key.as_tuple() for key in self.listing_keys],
            "quote_artifact_ids": [
                (key.as_tuple(), artifact_id) for key, artifact_id in self.quote_artifact_ids
            ],
            "dividend_artifact_ids": [
                (key.as_tuple(), artifact_id) for key, artifact_id in self.dividend_artifact_ids
            ],
            "aligned_calendar_id": self.aligned_calendar_id,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "observation_count": self.observation_count,
            "policy": self.policy.to_row(),
            "dependency_hash": self.dependency_hash,
            "eligibility": [item.to_row() for item in self.eligibility],
            "availability_reasons": list(self.availability_reasons),
        }


class MultivariateInputAdapter(Protocol):
    """Resolve explicit scoped records into the shared snapshot contract."""

    def resolve(
        self,
        *,
        dependencies: MultivariateInputDependencies,
        univariate_rows: Sequence[Mapping[str, Any]],
        policy: MonthlyDistributionEtfPolicy = DEFAULT_MONTHLY_DISTRIBUTION_ETF_POLICY,
    ) -> MultivariateInputSnapshot: ...


class ExplicitMultivariateInputAdapter:
    """Local and hosted adapter over an already-authorised dependency closure."""

    def resolve(
        self,
        *,
        dependencies: MultivariateInputDependencies,
        univariate_rows: Sequence[Mapping[str, Any]],
        policy: MonthlyDistributionEtfPolicy = DEFAULT_MONTHLY_DISTRIBUTION_ETF_POLICY,
    ) -> MultivariateInputSnapshot:
        return build_multivariate_input_snapshot(
            dependencies=dependencies, univariate_rows=univariate_rows, policy=policy
        )


def build_multivariate_input_snapshot(
    *,
    dependencies: MultivariateInputDependencies,
    univariate_rows: Sequence[Mapping[str, Any]],
    policy: MonthlyDistributionEtfPolicy = DEFAULT_MONTHLY_DISTRIBUTION_ETF_POLICY,
) -> MultivariateInputSnapshot:
    """Build an immutable snapshot without mutating or resolving upstream state."""

    results = tuple(
        sorted(
            (_eligibility(row, dependencies, policy) for row in univariate_rows),
            key=lambda item: item.listing,
        )
    )
    eligible_keys = tuple(item.listing for item in results if item.eligible)
    global_reasons = _global_reasons(dependencies, policy, eligible_keys)
    quote_ids = tuple(
        sorted(
            (key, dependencies.quote_artifact_ids[key])
            for key in eligible_keys
            if key in dependencies.quote_artifact_ids
        )
    )
    dividend_ids = tuple(
        sorted(
            (key, dependencies.dividend_artifact_ids[key])
            for key in eligible_keys
            if key in dependencies.dividend_artifact_ids
        )
    )
    payload = {
        "contract_version": INPUT_SNAPSHOT_CONTRACT.qualified_name,
        "project_id": dependencies.project_id,
        "project_snapshot_id": dependencies.project_snapshot_id,
        "metadata_selection_id": dependencies.metadata_selection_id,
        "univariate_run_id": dependencies.univariate_run_id,
        "univariate_selection_id": dependencies.univariate_selection_id,
        "bivariate_run_id": dependencies.bivariate_run_id or "",
        "listing_keys": [key.as_tuple() for key in eligible_keys],
        "quote_artifact_ids": [(key.as_tuple(), value) for key, value in quote_ids],
        "dividend_artifact_ids": [(key.as_tuple(), value) for key, value in dividend_ids],
        "aligned_calendar_id": dependencies.aligned_calendar_id or "",
        "date_start": dependencies.date_start or "",
        "date_end": dependencies.date_end or "",
        "observation_count": dependencies.observation_count,
        "policy": policy.to_row(),
        "availability_reasons": list(global_reasons),
    }
    dependency_hash = stable_contract_id("multivariate_dependency", payload)
    return MultivariateInputSnapshot(
        snapshot_id=stable_contract_id("multivariate_input_snapshot", payload),
        contract_version=INPUT_SNAPSHOT_CONTRACT,
        project_id=dependencies.project_id,
        project_snapshot_id=dependencies.project_snapshot_id,
        metadata_selection_id=dependencies.metadata_selection_id,
        univariate_run_id=dependencies.univariate_run_id,
        univariate_selection_id=dependencies.univariate_selection_id,
        bivariate_run_id=dependencies.bivariate_run_id or "",
        listing_keys=eligible_keys,
        quote_artifact_ids=quote_ids,
        dividend_artifact_ids=dividend_ids,
        aligned_calendar_id=dependencies.aligned_calendar_id or "",
        date_start=dependencies.date_start or "",
        date_end=dependencies.date_end or "",
        observation_count=dependencies.observation_count,
        policy=policy,
        dependency_hash=dependency_hash,
        eligibility=results,
        availability_reasons=global_reasons,
    )


def _eligibility(
    row: Mapping[str, Any],
    dependencies: MultivariateInputDependencies,
    policy: MonthlyDistributionEtfPolicy,
) -> EligibilityResult:
    key = MultivariateListingKey.from_row(row)
    reasons: list[str] = []
    if str(row.get("instrument_type", "")).upper() != policy.required_instrument_type.upper():
        reasons.append(REASON_NON_ETF)
    if str(row.get("distribution_frequency", "")).lower() != policy.required_distribution_frequency:
        reasons.append(REASON_NOT_MONTHLY)
    if policy.require_production_eligible_quotes and not bool(
        row.get("quote_history_production_eligible", True)
    ):
        reasons.append(REASON_MISSING_QUOTE_ARTIFACT)
    if key not in dependencies.quote_artifact_ids:
        reasons.append(REASON_MISSING_QUOTE_ARTIFACT)
    if key not in dependencies.dividend_artifact_ids:
        reasons.append(REASON_MISSING_DIVIDEND_ARTIFACT)
    return EligibilityResult(key, not reasons, tuple(sorted(set(reasons))))


def _global_reasons(
    dependencies: MultivariateInputDependencies,
    policy: MonthlyDistributionEtfPolicy,
    keys: tuple[MultivariateListingKey, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if dependencies.upstream_stale:
        reasons.append(REASON_STALE_UPSTREAM)
    if not dependencies.bivariate_run_id:
        reasons.append(REASON_MISSING_BIVARIATE_DEPENDENCY)
    elif dependencies.bivariate_status != "complete":
        reasons.append(REASON_BIVARIATE_NOT_COMPLETE)
    if len(keys) != len(set(keys)):
        reasons.append(REASON_DUPLICATE_LISTING_KEY)
    if tuple(sorted(keys)) != tuple(sorted(dependencies.bivariate_listing_keys)):
        reasons.append(REASON_MEMBERSHIP_MISMATCH)
    if (
        not dependencies.aligned_calendar_id
        or dependencies.aligned_calendar_id != dependencies.bivariate_aligned_calendar_id
    ):
        reasons.append(REASON_CALENDAR_MISMATCH)
    if dependencies.observation_count < policy.minimum_common_daily_return_observations:
        reasons.append(REASON_INSUFFICIENT_COMMON_HISTORY)
    if len(set(keys)) < policy.minimum_listing_count:
        reasons.append(REASON_FEWER_THAN_TWO_LISTINGS)
    return tuple(sorted(set(reasons)))


__all__ = [
    "ExplicitMultivariateInputAdapter",
    "EligibilityResult",
    "INPUT_SNAPSHOT_CONTRACT",
    "ListingKey",
    "MONTHLY_DISTRIBUTION_ETF_POLICY",
    "MonthlyDistributionEtfPolicy",
    "MultivariateInputAdapter",
    "MultivariateInputDependencies",
    "MultivariateInputSnapshot",
    "MultivariateListingKey",
    "build_multivariate_input_snapshot",
]
