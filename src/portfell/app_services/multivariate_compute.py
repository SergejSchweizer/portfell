"""Pure Multivariate computation and OOS DecisionArtifact selection."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Executor
from dataclasses import asdict, dataclass
from statistics import median
from typing import Any, cast

from portfell.app_services.analysis_compute import stable_hash
from portfell.income import (
    build_income_artifacts,
    build_income_evidence,
    normalize_distribution_events,
)
from portfell.multivariate_candidates import PortfolioCandidate, build_candidate_set
from portfell.multivariate_inputs import (
    MultivariateInputDependencies,
    MultivariateListingKey,
    build_multivariate_input_snapshot,
)
from portfell.multivariate_performance import build_multivariate_performance
from portfell.multivariate_quote_views import common_dates, first_price, last_price
from portfell.multivariate_refits import build_refitted_candidate_sets
from portfell.multivariate_risk_model import build_multivariate_risk_model
from portfell.multivariate_structural_walk_forward import (
    build_structural_walk_forward_evidence,
    structural_walk_forward_rows,
)
from portfell.multivariate_structure import build_multivariate_structure
from portfell.multivariate_structure_artifacts import build_structure_v2_documents
from portfell.multivariate_validation import (
    DEFAULT_WALK_FORWARD_POLICY,
    CandidateScorecard,
    ValidationScenario,
    ValidationSplit,
    build_candidate_scorecards,
    validate_candidate_stress,
    validate_candidates,
    walk_forward_validation_row,
)
from portfell.return_series import build_returns
from portfell.table_io import JsonRow

MULTIVARIATE_EXECUTION_VERSION = "multivariate_execution.clean.v1"
MULTIVARIATE_PHASES = (
    "inputs",
    "risk_model_and_candidates",
    "walk_forward_validation",
    "scorecards",
    "structural_diagnostics",
    "decision",
    "artifact_persistence",
    "complete",
)


@dataclass(frozen=True)
class MultivariateDecision:
    objective: str
    winning_candidate_id: str
    requested_method: str
    actual_method: str
    available: bool
    production_eligible: bool
    reason: str | None
    document: JsonRow


@dataclass(frozen=True)
class MultivariateComputation:
    input_snapshot_id: str
    logical_hash: str
    algorithm_version: str
    documents: Mapping[str, JsonRow | list[JsonRow]]
    decision: MultivariateDecision


def compute_multivariate(
    *,
    universe_id: str,
    univariate_run_id: str,
    selection_id: str,
    bivariate_run_id: str,
    market_snapshot_id: str,
    selected_rows: Sequence[Mapping[str, Any]],
    listing_metadata: Sequence[Mapping[str, Any]],
    quote_rows: Sequence[Mapping[str, Any]],
    dividend_rows: Sequence[Mapping[str, Any]],
    objective: str,
    executor: Executor,
    on_phase: Callable[[int, str], None] | None = None,
) -> MultivariateComputation:
    """Compute all immutable Multivariate evidence from one pinned source snapshot."""

    if objective not in {"return_risk", "return_drawdown", "minimum_risk"}:
        raise ValueError("invalid_multivariate_objective")
    metadata = {
        (str(row.get("isin", "")), str(row.get("exchange", "")), str(row.get("code", ""))): row
        for row in listing_metadata
    }
    selected = tuple(
        {
            **metadata.get(
                (str(row.get("isin", "")), str(row.get("exchange", "")), str(row.get("code", ""))),
                {},
            ),
            **row,
        }
        for row in selected_rows
    )
    # Returns are always derived from the quote rows supplied by the local
    # shared-storage market gateway.  Keeping this input mandatory prevents a
    # caller from silently substituting a PostgreSQL return artifact.
    returns = build_returns(quote_rows)
    keys = tuple(sorted(MultivariateListingKey.from_row(row) for row in selected))
    calendar_dates = common_dates(cast(list[JsonRow], returns), keys)
    calendar_id = stable_hash(
        {"listing_keys": [key.as_tuple() for key in keys], "dates": calendar_dates}
    )
    logical_hash = stable_hash(
        {
            "universe_id": universe_id,
            "univariate_run_id": univariate_run_id,
            "selection_id": selection_id,
            "bivariate_run_id": bivariate_run_id,
            "market_snapshot_id": market_snapshot_id,
            "objective": objective,
            "execution_version": MULTIVARIATE_EXECUTION_VERSION,
        }
    )
    dependencies = MultivariateInputDependencies(
        project_id="default",
        project_snapshot_id=logical_hash,
        metadata_selection_id=universe_id,
        univariate_run_id=univariate_run_id,
        univariate_selection_id=selection_id,
        bivariate_run_id=bivariate_run_id,
        bivariate_status="complete",
        bivariate_listing_keys=keys,
        aligned_calendar_id=calendar_id,
        bivariate_aligned_calendar_id=calendar_id,
        date_start=calendar_dates[0] if calendar_dates else None,
        date_end=calendar_dates[-1] if calendar_dates else None,
        observation_count=len(calendar_dates),
        quote_artifact_ids={
            key: f"quote:{market_snapshot_id}:{key.isin}:{key.exchange}:{key.code}" for key in keys
        },
        dividend_artifact_ids={
            key: f"dividend:{market_snapshot_id}:{key.isin}:{key.exchange}:{key.code}"
            for key in keys
        },
    )
    snapshot = build_multivariate_input_snapshot(
        dependencies=dependencies, univariate_rows=selected
    )
    if on_phase is not None:
        on_phase(1, MULTIVARIATE_PHASES[0])
    risk = build_multivariate_risk_model(snapshot=snapshot, return_rows=returns)
    structure = build_multivariate_structure(risk)
    quote_json_rows = tuple(dict(row) for row in quote_rows)
    income = {
        key: build_income_evidence(
            listing=key,
            events=normalize_distribution_events(dividend_rows, listing=key),
            period_end=snapshot.date_end or "1970-01-01",
            denominator_price=last_price(quote_json_rows, key),
            period_start=snapshot.date_start,
            start_price=first_price(quote_json_rows, key),
        )
        for key in keys
    }
    candidates = build_candidate_set(
        snapshot=snapshot,
        risk_model=risk,
        return_rows=returns,
        income=income,
        executor=executor,
    )
    refitted = build_refitted_candidate_sets(
        executor=executor,
        candidates=candidates,
        snapshot=snapshot,
        return_rows=returns,
        income=income,
    )
    if on_phase is not None:
        on_phase(2, MULTIVARIATE_PHASES[1])
    validation = validate_candidates(
        candidates=candidates,
        return_rows=returns,
        precomputed_candidates=refitted,
        risk_model_id=risk.risk_model_id,
        executor=executor,
    )
    if on_phase is not None:
        on_phase(3, MULTIVARIATE_PHASES[2])
    structure_v2 = build_structure_v2_documents(
        risk_model=risk,
        return_rows=returns,
        candidates=candidates,
    )
    structural_walk_forward = build_structural_walk_forward_evidence(
        snapshot=snapshot,
        candidates=candidates,
        return_rows=returns,
        refitted_candidate_sets=refitted,
        validation_splits=validation,
    )
    scenarios = validate_candidate_stress(
        candidates=candidates, return_rows=returns, executor=executor
    )
    scorecards = build_candidate_scorecards(splits=validation, scenarios=scenarios)
    if on_phase is not None:
        on_phase(4, MULTIVARIATE_PHASES[3])
        on_phase(5, MULTIVARIATE_PHASES[4])
    decision = _select_decision(
        objective=objective,
        candidates=candidates,
        scorecards=scorecards,
        splits=validation,
        scenarios=scenarios,
    )
    if on_phase is not None:
        on_phase(6, MULTIVARIATE_PHASES[5])
    candidate_rows = [_candidate_row(item) for item in candidates]
    risk_contributions = [
        {
            "candidate_id": candidate.candidate_id,
            "method": candidate.method,
            "isin": contribution.listing.isin,
            "exchange": contribution.listing.exchange,
            "code": contribution.listing.code,
            "weight": contribution.weight,
            "marginal_risk_contribution": contribution.marginal_risk_contribution,
            "absolute_risk_contribution": contribution.absolute_risk_contribution,
            "percent_risk_contribution": contribution.percent_risk_contribution,
        }
        for candidate in candidates
        for contribution in candidate.risk_contributions
    ]
    income_rows = [_income_row(key, evidence) for key, evidence in sorted(income.items())]
    validation_rows = (
        [walk_forward_validation_row(item) for item in validation]
        + [{"kind": "stress", **asdict(item)} for item in scenarios]
        + [{"kind": "scorecard", **asdict(item)} for item in scorecards]
    )
    documents: dict[str, JsonRow] = {
        "summary": {
            "input_snapshot_id": snapshot.snapshot_id,
            "market_source_snapshot_id": market_snapshot_id,
            "risk_model_id": risk.risk_model_id,
            "candidate_etf_count": len(snapshot.listing_keys),
            "aligned_period": {
                "date_start": snapshot.date_start,
                "date_end": snapshot.date_end,
                "observation_count": snapshot.observation_count,
            },
            "availability_reasons": list(snapshot.availability_reasons),
            "objective": objective,
        },
        "input_snapshot": snapshot.to_row(),
        "risk_model": {
            "risk_model_id": risk.risk_model_id,
            "input_snapshot_id": risk.input_snapshot_id,
            "contract_version": risk.contract_version.qualified_name,
            "estimator": risk.estimator,
            "return_type": risk.return_type,
            "window_policy": risk.window_policy,
            "estimator_parameters": list(risk.estimator_parameters),
            "listing_keys": [item.as_tuple() for item in risk.listings],
            "aligned_calendar_id": risk.aligned_calendar_id,
            "date_start": risk.date_start,
            "date_end": risk.date_end,
            "observation_count": risk.observation_count,
            "covariance": [list(row) for row in risk.covariance],
            "shrinkage_intensity": risk.shrinkage_intensity,
            "minimum_eigenvalue": risk.minimum_eigenvalue,
            "condition_number": risk.condition_number,
            "is_positive_semidefinite": risk.is_positive_semidefinite,
            "availability_reasons": list(risk.availability_reasons),
            "algorithm_version": risk.algorithm_version,
        },
        "structure": {
            **structure.summary(),
            "eigenvalues": list(structure.eigenvalues),
            "explained_variance": list(structure.explained_variance),
            "cumulative_explained_variance": list(structure.cumulative_explained_variance),
            "clusters": [
                {
                    "isin": key.isin,
                    "exchange": key.exchange,
                    "code": key.code,
                    "cluster": cluster,
                }
                for key, cluster in structure.cluster_by_listing
            ],
        },
        "multivariate.structure@v2": structure_v2.structure,
        "multivariate.candidate_structure@v2": structure_v2.candidate_structure,
        "multivariate.structural_walk_forward@v1": {
            "items": list(structural_walk_forward_rows(structural_walk_forward))
        },
        "candidates": {"items": candidate_rows},
        "validation": {"items": validation_rows},
        "risk_contributions": {"items": risk_contributions},
        "income_evidence": {"items": income_rows},
        "performance": build_multivariate_performance(candidates=candidates, return_rows=returns),
        "decision": decision.document,
        "market_source": {
            "snapshot_id": market_snapshot_id,
            "split_policy": "lineage_only_no_return_adjustment",
        },
    }
    for name, value in build_income_artifacts(
        evidence_by_listing=income,
        dividend_rows=dividend_rows,
        income_metrics=income_rows,
    ).items():
        documents[name] = cast(JsonRow, value)
    return MultivariateComputation(
        input_snapshot_id=snapshot.snapshot_id,
        logical_hash=logical_hash,
        algorithm_version=MULTIVARIATE_EXECUTION_VERSION,
        documents=documents,
        decision=decision,
    )


def _select_decision(
    *,
    objective: str,
    candidates: Sequence[PortfolioCandidate],
    scorecards: Sequence[CandidateScorecard],
    splits: Sequence[ValidationSplit],
    scenarios: Sequence[ValidationScenario],
) -> MultivariateDecision:
    candidate_by_id = {item.candidate_id: item for item in candidates}
    scored: list[tuple[float, str, CandidateScorecard]] = []
    for scorecard in scorecards:
        candidate = candidate_by_id.get(scorecard.candidate_id)
        if candidate is None or candidate.status != "feasible":
            continue
        score = _objective_score(objective, scorecard, splits)
        if score is not None:
            scored.append((score, scorecard.candidate_id, scorecard))
    if not scored:
        return MultivariateDecision(
            objective=objective,
            winning_candidate_id="unavailable",
            requested_method="unavailable",
            actual_method="unavailable",
            available=False,
            production_eligible=False,
            reason="oos_decision_evidence_unavailable",
            document={
                "objective": objective,
                "available": False,
                "production_eligible": False,
                "reason": "oos_decision_evidence_unavailable",
                "ranking_basis": "walk_forward_out_of_sample_only",
            },
        )
    score, candidate_id, scorecard = sorted(scored, key=lambda item: (-item[0], item[1]))[0]
    candidate = candidate_by_id[candidate_id]
    scenario_reasons = sorted(
        {
            str(item.reason)
            for item in scenarios
            if item.candidate_id == candidate_id and item.reason is not None
        }
    )
    production_eligible = (
        scorecard.completed_split_count >= DEFAULT_WALK_FORWARD_POLICY.minimum_completed_splits
        and not scorecard.availability_reasons
        and not scenario_reasons
    )
    document: JsonRow = {
        "objective": objective,
        "winning_candidate_id": candidate_id,
        "requested_method": candidate.method,
        "actual_method": candidate.method,
        "available": True,
        "production_eligible": production_eligible,
        "ranking_basis": "walk_forward_out_of_sample_only",
        "objective_score": score,
        "completed_split_count": scorecard.completed_split_count,
        "median_post_cost_return": scorecard.median_post_cost_return,
        "median_volatility": scorecard.median_volatility,
        "availability_reasons": list(scorecard.availability_reasons),
        "scenario_reasons": scenario_reasons,
        "tie_break": "candidate_id_ascending",
    }
    return MultivariateDecision(
        objective=objective,
        winning_candidate_id=candidate_id,
        requested_method=candidate.method,
        actual_method=candidate.method,
        available=True,
        production_eligible=production_eligible,
        reason=None if production_eligible else "candidate_not_production_eligible",
        document=document,
    )


def _objective_score(
    objective: str, scorecard: CandidateScorecard, splits: Sequence[ValidationSplit]
) -> float | None:
    minimum = DEFAULT_WALK_FORWARD_POLICY.minimum_completed_splits
    if scorecard.completed_split_count < minimum or scorecard.median_volatility is None:
        return None
    volatility = scorecard.median_volatility
    if objective == "minimum_risk":
        return -volatility
    if scorecard.median_post_cost_return is None:
        return None
    if objective == "return_risk":
        return None if volatility <= 0 else scorecard.median_post_cost_return / volatility
    drawdowns = [
        abs(item.max_drawdown)
        for item in splits
        if item.candidate_id == scorecard.candidate_id
        and item.status == "complete"
        and item.max_drawdown is not None
    ]
    if not drawdowns:
        return None
    denominator = median(drawdowns)
    return None if denominator <= 0 else scorecard.median_post_cost_return / denominator


def _candidate_row(item: PortfolioCandidate) -> JsonRow:
    return {
        "candidate_id": item.candidate_id,
        "method": item.method,
        "baseline": item.baseline,
        "status": item.status,
        "reasons": list(item.reasons),
        "weights": [
            {"isin": key.isin, "exchange": key.exchange, "code": key.code, "weight": weight}
            for key, weight in item.weights
        ],
        "variance": item.variance,
        "volatility": item.volatility,
        "var": item.var,
        "cvar": item.cvar,
        "maximum_weight": item.maximum_weight,
        "herfindahl_index": item.herfindahl_index,
        "effective_holding_count": item.effective_holding_count,
        "gross_ttm_distribution_yield": item.gross_ttm_distribution_yield,
        "gross_monthly_distribution": item.gross_monthly_distribution,
        "total_return": item.total_return,
        "average_monthly_return": item.average_monthly_return,
        "average_annual_return": item.average_annual_return,
        "max_drawdown": item.max_drawdown,
        "diversification_ratio": item.diversification_ratio,
    }


def _income_row(key: MultivariateListingKey, evidence: object) -> JsonRow:
    row = cast(Any, evidence)
    return {
        "isin": key.isin,
        "exchange": key.exchange,
        "code": key.code,
        "currency": row.currency,
        "event_count": row.event_count,
        "observed_month_count": row.observed_month_count,
        "observed_payment_coverage": row.observed_payment_coverage,
        "gross_ttm_distribution_amount": row.gross_ttm_distribution_amount,
        "gross_ttm_distribution_yield": row.gross_ttm_distribution_yield,
        "mean_observed_monthly_distribution": row.mean_observed_monthly_distribution,
        "median_observed_monthly_distribution": row.median_observed_monthly_distribution,
        "lower_percentile_monthly_distribution": row.lower_percentile_monthly_distribution,
        "coefficient_of_variation": row.coefficient_of_variation,
        "cut_count": row.cut_count,
        "largest_cut": row.largest_cut,
        "longest_falling_sequence": row.longest_falling_sequence,
        "distribution_trend": row.distribution_trend,
        "price_return": row.price_return,
        "total_return": row.total_return,
        "distribution_to_total_return_gap": row.distribution_to_total_return_gap,
        "market_price_capital_change": row.market_price_capital_change,
        "availability_reasons": list(row.availability_reasons),
        "warnings": list(row.warnings),
    }
