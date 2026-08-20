"""Composition-only selector pipeline; child algorithms remain authoritative."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from portfell.multivariate.contracts.common import (
    DecisionStageId,
    EvidenceAvailability,
    ListingIdentity,
)
from portfell.multivariate.contracts.decision_reasons import DecisionReasonCode
from portfell.multivariate.contracts.decisions import (
    DecisionArtifact,
    DecisionCandidate,
    DecisionRejection,
)
from portfell.multivariate.contracts.history import ResearchStage, ResearchUniverseSnapshot
from portfell.multivariate.selector.eligibility import EligibilityResult, SelectorMetrics, apply_eligibility
from portfell.multivariate.selector.pareto import ParetoResult, select_pareto
from portfell.multivariate.selector.redundancy import (
    RedundancyCandidate,
    RedundancyResult,
    reduce_redundancy,
)


@dataclass(frozen=True, slots=True)
class SelectorEvidenceContext:
    run_id: str
    objective: str
    project_slug: str
    pinned_revision: str
    algorithm_version: str
    profile_version: str


@dataclass(frozen=True, slots=True)
class SelectorPipelineResult:
    eligibility: EligibilityResult
    pareto: ParetoResult
    redundancy: RedundancyResult
    decisions: tuple[DecisionArtifact, ...]
    snapshots: tuple[ResearchUniverseSnapshot, ...]

    @property
    def selected(self) -> tuple[ListingIdentity, ...]:
        return self.redundancy.selected


def _snapshot(
    *,
    context: SelectorEvidenceContext,
    listings: tuple[ListingIdentity, ...],
    removed_count: int,
    removal_reasons: dict[str, int],
    availability: EvidenceAvailability = EvidenceAvailability.AVAILABLE,
) -> ResearchUniverseSnapshot:
    return ResearchUniverseSnapshot(
        project_slug=context.project_slug,
        revision=context.pinned_revision,
        stage=ResearchStage.MULTIVARIATE,
        availability=availability,
        listing_count=len(listings),
        unique_isin_count=len({listing.isin for listing in listings}),
        removed_count=removed_count,
        removal_reasons=removal_reasons,
    )


def _decision(
    *,
    context: SelectorEvidenceContext,
    stage: DecisionStageId,
    before: tuple[ListingIdentity, ...],
    after: tuple[ListingIdentity, ...],
    rejections: tuple[DecisionRejection, ...],
    status: EvidenceAvailability,
    reason_code: DecisionReasonCode,
) -> DecisionArtifact:
    return DecisionArtifact(
        run_id=context.run_id,
        objective=context.objective,
        stage=stage,
        pinned_revisions=(context.pinned_revision,),
        candidates=tuple(DecisionCandidate(listing.token) for listing in before),
        selected_ids=tuple(listing.token for listing in after),
        rejections=rejections,
        status=status,
        reason_code=reason_code,
        algorithm_version=context.algorithm_version,
        profile_version=context.profile_version,
        listing_scope=before,
    )


def select_optimizer_universe(
    rows: tuple[SelectorMetrics, ...],
    *,
    correlations: dict[tuple[ListingIdentity, ListingIdentity], float],
    evidence_context: SelectorEvidenceContext,
    allowed_distribution_frequencies: tuple[str, ...] = (),
    minimum_size: int = 1,
    maximum_size: int = 250,
) -> SelectorPipelineResult:
    """Compose eligibility -> Pareto -> redundancy and immutable audit evidence."""

    eligibility = apply_eligibility(
        rows,
        allowed_distribution_frequencies=allowed_distribution_frequencies,
    )
    pareto = select_pareto(eligibility.eligible, minimum_size=minimum_size)
    by_listing = {row.listing: row for row in eligibility.eligible}
    candidates = tuple(
        RedundancyCandidate(
            listing=member.listing,
            pareto_rank=member.rank,
            sortino=float(by_listing[member.listing].sortino),
            annualized_geometric_return=float(by_listing[member.listing].annualized_geometric_return),
            expected_shortfall=float(by_listing[member.listing].expected_shortfall),
            annualized_volatility=float(by_listing[member.listing].annualized_volatility),
        )
        for member in pareto.selected
    )
    redundancy = reduce_redundancy(
        candidates,
        correlations=correlations,
        maximum_size=maximum_size,
    )

    input_listings = tuple(sorted(row.listing for row in rows))
    eligibility_listings = tuple(sorted(row.listing for row in eligibility.eligible))
    pareto_listings = tuple(sorted(member.listing for member in pareto.selected))
    final_listings = tuple(sorted(redundancy.selected))

    eligibility_reasons = Counter(reason.value for _, reason in eligibility.rejected)
    eligibility_decision = _decision(
        context=evidence_context,
        stage=DecisionStageId.INPUT_ELIGIBILITY,
        before=input_listings,
        after=eligibility_listings,
        rejections=tuple(
            DecisionRejection(listing.token, reason) for listing, reason in eligibility.rejected
        ),
        status=EvidenceAvailability.AVAILABLE,
        reason_code=DecisionReasonCode.ELIGIBLE,
    )
    pareto_decision = _decision(
        context=evidence_context,
        stage=DecisionStageId.UNIVARIATE_PARETO,
        before=eligibility_listings,
        after=pareto_listings,
        rejections=tuple(
            DecisionRejection(member.listing.token, DecisionReasonCode.PARETO_DOMINATED)
            for member in pareto.dominated
        ),
        status=EvidenceAvailability.AVAILABLE,
        reason_code=DecisionReasonCode.PARETO_SELECTED,
    )
    redundancy_status = (
        EvidenceAvailability.AVAILABLE
        if redundancy.applied
        else EvidenceAvailability.NOT_APPLICABLE
    )
    redundancy_reason = (
        DecisionReasonCode.REDUNDANCY_REPRESENTED
        if redundancy.applied
        else DecisionReasonCode.REDUNDANCY_NOT_REQUIRED
    )
    redundancy_decision = _decision(
        context=evidence_context,
        stage=DecisionStageId.BIVARIATE_REDUNDANCY,
        before=pareto_listings,
        after=final_listings,
        rejections=tuple(
            DecisionRejection(
                item.listing.token,
                DecisionReasonCode.REDUNDANCY_REPRESENTED,
                {"representative": item.representative.token, "pearson": item.pearson},
            )
            for item in redundancy.rejected
        ),
        status=redundancy_status,
        reason_code=redundancy_reason,
    )
    snapshots = (
        _snapshot(
            context=evidence_context,
            listings=input_listings,
            removed_count=0,
            removal_reasons={},
        ),
        _snapshot(
            context=evidence_context,
            listings=eligibility_listings,
            removed_count=len(eligibility.rejected),
            removal_reasons=dict(sorted(eligibility_reasons.items())),
        ),
        _snapshot(
            context=evidence_context,
            listings=pareto_listings,
            removed_count=len(pareto.dominated),
            removal_reasons={DecisionReasonCode.PARETO_DOMINATED.value: len(pareto.dominated)},
        ),
        _snapshot(
            context=evidence_context,
            listings=final_listings,
            removed_count=len(redundancy.rejected),
            removal_reasons={redundancy_reason.value: len(redundancy.rejected)},
            availability=redundancy_status,
        ),
    )
    return SelectorPipelineResult(
        eligibility,
        pareto,
        redundancy,
        (eligibility_decision, pareto_decision, redundancy_decision),
        snapshots,
    )
