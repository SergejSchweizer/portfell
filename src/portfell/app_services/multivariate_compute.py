"""Pure Multivariate computation and OOS DecisionArtifact selection."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Executor
from dataclasses import asdict, dataclass
from typing import Any, cast

from portfell.app_services.analysis_compute import stable_hash
from portfell.contract_versioning import ContractVersion
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
from portfell.multivariate_risk_model_comparison import (
    build_current_sample_candidate_family,
    build_risk_model_comparison,
)
from portfell.multivariate_risk_spec import LW_FULL
from portfell.multivariate_risk_stress import correlation_convergence_25pct, volatility_up_25pct
from portfell.multivariate_structural_walk_forward import (
    build_structural_walk_forward_evidence,
    structural_walk_forward_rows,
)
from portfell.multivariate_structure import build_multivariate_structure
from portfell.multivariate_structure_artifacts import build_structure_v2_documents
from portfell.multivariate_validation import (
    build_candidate_scorecards,
    validate_candidate_stress,
    validate_candidates,
    walk_forward_validation_row,
)
from portfell.return_series import build_returns
from portfell.table_io import JsonRow

DECISION_CONTRACT = ContractVersion("multivariate.decision", 2)

MULTIVARIATE_EXECUTION_VERSION = "multivariate_execution.clean.v19"
DEFAULT_MULTIVARIATE_CPUS = 80
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
    checkpoint: Mapping[str, object] | None = None,
    save_checkpoint: Callable[[int, str, Mapping[str, object]], None] | None = None,
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
    calendar_dates = common_dates(returns, keys)
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
    state: dict[str, Any] = dict(checkpoint or {})
    resumed_phase = state.get("phase", 0)
    phase = int(resumed_phase) if isinstance(resumed_phase, int) else 0
    if phase > 0 and on_phase is not None:
        on_phase(phase, f"resuming_from_checkpoint_{MULTIVARIATE_PHASES[phase - 1]}")

    if phase < 2:
        if on_phase is not None:
            on_phase(1, MULTIVARIATE_PHASES[0])
        risk = build_multivariate_risk_model(snapshot=snapshot, return_rows=returns, spec=LW_FULL)
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
            risk_model_spec=LW_FULL,
        )
        state = {
            "phase": 2,
            "risk": risk,
            "structure": structure,
            "income": income,
            "candidates": candidates,
            "refitted": refitted,
        }
        if save_checkpoint is not None:
            save_checkpoint(2, MULTIVARIATE_PHASES[1], state)
    else:
        risk = state["risk"]
        structure = state["structure"]
        income = state["income"]
        candidates = state["candidates"]
        refitted = state["refitted"]

    if on_phase is not None and phase < 2:
        on_phase(2, MULTIVARIATE_PHASES[1])
    if phase < 3:
        validation = validate_candidates(
            candidates=candidates,
            return_rows=returns,
            precomputed_candidates=refitted,
            risk_model_id=risk.risk_model_id,
            executor=executor,
        )
        state.update({"phase": 3, "validation": validation})
        if save_checkpoint is not None:
            save_checkpoint(3, MULTIVARIATE_PHASES[2], state)
    else:
        validation = state["validation"]

    if on_phase is not None and phase < 3:
        on_phase(3, MULTIVARIATE_PHASES[2])
    if phase < 5:
        structure_v2 = build_structure_v2_documents(
            risk_model=risk, return_rows=returns, candidates=candidates
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
        risk_model_comparison = build_risk_model_comparison(
            snapshot=snapshot, return_rows=returns, income=income, executor=executor
        )
        current_sample_family = build_current_sample_candidate_family(
            snapshot=snapshot,
            return_rows=returns,
            income=income,
            executor=executor,
        )
        scorecards = build_candidate_scorecards(splits=validation, scenarios=scenarios)
        state.update(
            {
                "phase": 5,
                "structure_v2": structure_v2,
                "structural_walk_forward": structural_walk_forward,
                "scenarios": scenarios,
                "scorecards": scorecards,
                "current_sample_family": current_sample_family,
                "risk_model_comparison": risk_model_comparison,
            }
        )
        if save_checkpoint is not None:
            save_checkpoint(5, MULTIVARIATE_PHASES[4], state)
    else:
        structure_v2 = state["structure_v2"]
        structural_walk_forward = state["structural_walk_forward"]
        scenarios = state["scenarios"]
        scorecards = state["scorecards"]
        current_sample_family = state.get("current_sample_family")
        risk_model_comparison = state.get("risk_model_comparison", {})
        if current_sample_family is None:
            current_sample_family = build_current_sample_candidate_family(
                snapshot=snapshot,
                return_rows=returns,
                income=income,
                executor=executor,
            )

    if on_phase is not None and phase < 5:
        on_phase(4, MULTIVARIATE_PHASES[3])
        on_phase(5, MULTIVARIATE_PHASES[4])
    decision = _select_common_oos_decision(
        objective=objective,
        risk_model_comparison=risk_model_comparison,
        current_sample_candidates=current_sample_family.candidates,
    )
    state.update({"phase": 6, "decision": decision})
    if save_checkpoint is not None:
        save_checkpoint(6, MULTIVARIATE_PHASES[5], state)
    if on_phase is not None and phase < 6:
        on_phase(6, MULTIVARIATE_PHASES[5])
    current_candidates = tuple(current_sample_family.candidates)
    candidate_rows = [_candidate_row(item) for item in current_candidates]
    risk_contributions = [
        {
            "candidate_id": candidate.candidate_id,
            "candidate_configuration_id": candidate.candidate_configuration_id,
            "risk_model_id": candidate.risk_model_id,
            "risk_model_spec_key": candidate.risk_model_spec_key,
            "risk_model_spec_id": candidate.risk_model_spec_id,
            "fit_calendar_id": candidate.fit_calendar_id,
            "evidence_role": "descriptive",
            "method": candidate.method,
            "isin": contribution.listing.isin,
            "exchange": contribution.listing.exchange,
            "code": contribution.listing.code,
            "weight": contribution.weight,
            "marginal_risk_contribution": contribution.marginal_risk_contribution,
            "absolute_risk_contribution": contribution.absolute_risk_contribution,
            "percent_risk_contribution": contribution.percent_risk_contribution,
        }
        for candidate in current_candidates
        for contribution in candidate.risk_contributions
    ]
    risk_stress_rows = [
        result.to_row()
        for candidate in current_candidates
        for result in (
            volatility_up_25pct(
                risk_model=current_sample_family.model(candidate.risk_model_spec_key),
                candidate=candidate,
            ),
            correlation_convergence_25pct(
                risk_model=current_sample_family.model(candidate.risk_model_spec_key),
                candidate=candidate,
            ),
        )
    ]
    income_rows = [_income_row(key, evidence) for key, evidence in sorted(income.items())]
    validation_rows = (
        [
            {"evidence_role": "descriptive", **walk_forward_validation_row(item)}
            for item in validation
        ]
        + [{"kind": "stress", "evidence_role": "descriptive", **asdict(item)} for item in scenarios]
        + [
            {"kind": "scorecard", "evidence_role": "descriptive", **asdict(item)}
            for item in scorecards
        ]
        + [
            {"kind": "common_oos_validation", "evidence_role": "selection", **row}
            for row in risk_model_comparison.get("common_oos_validation", [])
        ]
        + [
            {"kind": "configuration_scorecard", "evidence_role": "selection", **row}
            for row in risk_model_comparison.get("configuration_scorecards", [])
        ]
        + [
            {"kind": "configuration_ranking", "evidence_role": "selection", **row}
            for row in risk_model_comparison.get("configuration_rankings", {}).get(objective, [])
        ]
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
            "fit_calendar_id": risk.fit_calendar_id,
            "spec_key": risk.spec_key,
            "spec_id": risk.spec_id,
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
        "risk_stress": {"items": risk_stress_rows},
        "risk_model_comparison": risk_model_comparison,
        "income_evidence": {"items": income_rows},
        "current_sample_family": {"items": list(current_sample_family.to_rows())},
        "performance": build_multivariate_performance(
            candidates=current_candidates, return_rows=returns
        ),
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


def _select_common_oos_decision(
    *,
    objective: str,
    risk_model_comparison: Mapping[str, Any],
    current_sample_candidates: Sequence[PortfolioCandidate] = (),
) -> MultivariateDecision:
    """Select only from persisted configuration-keyed common-OOS rankings."""
    rankings = risk_model_comparison.get("configuration_rankings", {})
    ordered = tuple(rankings.get(objective, ()))
    if not ordered:
        document: JsonRow = {
            "contract_version": DECISION_CONTRACT.qualified_name,
            "objective": objective,
            "available": False,
            "production_eligible": False,
            "reason": "common_oos_decision_evidence_unavailable",
            "ranking_basis": "common_oos_14_configuration_only",
            "selection_authority": "common_oos_14_config",
        }
        return MultivariateDecision(
            objective=objective,
            winning_candidate_id="unavailable",
            requested_method="unavailable",
            actual_method="unavailable",
            available=False,
            production_eligible=False,
            reason="common_oos_decision_evidence_unavailable",
            document=document,
        )
    winner = ordered[0]
    current_by_configuration = {
        candidate.candidate_configuration_id: candidate for candidate in current_sample_candidates
    }
    current = current_by_configuration.get(str(winner.get("configuration_id", "")))
    available = (
        int(winner.get("completed_split_count", 0)) >= 2
        and current is not None
        and current.status == "feasible"
    )
    document = {
        "contract_version": DECISION_CONTRACT.qualified_name,
        "objective": objective,
        "objective_metric": "median_sharpe_ratio"
        if objective == "return_risk"
        else (
            "median_return_drawdown_ratio"
            if objective == "return_drawdown"
            else "minimum_volatility"
        ),
        "winning_candidate_id": current.candidate_id
        if available and current is not None
        else "unavailable",
        "winning_configuration_id": winner.get("configuration_id", "unavailable"),
        "requested_method": winner.get("method", "unavailable"),
        "actual_method": winner.get("method", "unavailable"),
        "risk_model_spec_key": winner.get("spec_key", ""),
        "risk_model_spec_id": winner.get("risk_model_spec_id", ""),
        "risk_model_id": current.risk_model_id if current is not None else None,
        "fit_calendar_id": current.fit_calendar_id if current is not None else "",
        "available": available,
        "production_eligible": available,
        "reason": None if available else "common_oos_decision_evidence_unavailable",
        "ranking_basis": "common_oos_14_configuration_only",
        "selection_authority": "common_oos_14_config",
        "objective_score": winner.get("objective_score"),
        "comparison_split_count": winner.get("completed_split_count", 0),
        "median_turnover": winner.get("median_turnover"),
        "median_herfindahl_index": winner.get("median_herfindahl_index"),
        "tie_break": (
            "median_turnover_ascending_then_median_hhi_ascending_then_configuration_id_ascending"
        ),
        "full_history_evidence_role": "descriptive_non_selection",
    }
    return MultivariateDecision(
        objective=objective,
        winning_candidate_id=current.candidate_id
        if available and current is not None
        else "unavailable",
        requested_method=str(winner.get("method", "unavailable")) if available else "unavailable",
        actual_method=str(winner.get("method", "unavailable")) if available else "unavailable",
        available=available,
        production_eligible=available,
        reason=None if available else "common_oos_decision_evidence_unavailable",
        document=document,
    )


def _candidate_row(item: PortfolioCandidate) -> JsonRow:
    return {
        "candidate_id": item.candidate_id,
        "candidate_configuration_id": item.candidate_configuration_id,
        "risk_model_id": item.risk_model_id,
        "risk_model_spec_key": item.risk_model_spec_key,
        "risk_model_spec_id": item.risk_model_spec_id,
        "fit_calendar_id": item.fit_calendar_id,
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
