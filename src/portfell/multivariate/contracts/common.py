"""Common immutable identities shared by all Multivariate work orders."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, order=True, slots=True)
class ListingIdentity:
    isin: str
    exchange: str
    code: str

    def __post_init__(self) -> None:
        if not self.isin or not self.exchange or not self.code:
            raise ValueError("listing identity requires isin, exchange, and code")

    @property
    def token(self) -> str:
        return f"{self.isin}|{self.exchange}|{self.code}"


class DecisionStageId(StrEnum):
    INPUT_ELIGIBILITY = "input_eligibility"
    UNIVARIATE_PARETO = "univariate_pareto"
    BIVARIATE_REDUNDANCY = "bivariate_redundancy"
    RISK_MODEL_CANDIDATES = "risk_model_candidates"
    PORTFOLIO_CANDIDATES = "portfolio_candidates"
    WALK_FORWARD_VALIDATION = "walk_forward_validation"
    WINNER_SELECTION = "winner_selection"
    FINAL_PORTFOLIO = "final_portfolio"


DECISION_STAGE_ORDER: tuple[DecisionStageId, ...] = tuple(DecisionStageId)


class EvidenceAvailability(StrEnum):
    AVAILABLE = "available"
    NOT_RUN = "not_run"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class AttemptEnvelope:
    logical_id: str
    attempt: int
    availability: EvidenceAvailability
    error_code: str | None = None
    public_message: str | None = None

    def __post_init__(self) -> None:
        if not self.logical_id:
            raise ValueError("logical_id is required")
        if self.attempt < 1:
            raise ValueError("attempt numbering starts at one")
        if self.availability is EvidenceAvailability.AVAILABLE and self.error_code is not None:
            raise ValueError("available evidence cannot carry an error code")
