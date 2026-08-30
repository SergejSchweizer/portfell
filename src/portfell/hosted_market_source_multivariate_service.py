"""Multivariate research service backed exclusively by one external market snapshot."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import replace
from typing import cast

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_service_support import stable_hash
from portfell.hosted_api_state import MultivariateRunRecord
from portfell.hosted_market_source_research_data import (
    MarketResearchSnapshot,
    MarketSourceResearchData,
)
from portfell.hosted_multivariate_run_repository import MultivariateRunRepository
from portfell.hosted_multivariate_service import MultivariateResearchService
from portfell.hosted_repository_importer import ProjectRepository
from portfell.hosted_research_ports import (
    ResearchDataPort,
    ResearchPersistencePort,
    ResearchRunRepository,
)
from portfell.hosted_research_workflow import (
    UnivariateSelection,
    bivariate_source_id,
    univariate_source_id,
)
from portfell.hosted_selection_repository import SelectionRepository
from portfell.income import (
    build_income_artifacts,
    build_income_evidence,
    normalize_distribution_events,
)
from portfell.market_source.errors import MarketSourceError
from portfell.market_source.projection import MarketProjectionError
from portfell.multivariate_candidates import build_candidate_set
from portfell.multivariate_inputs import (
    MultivariateInputDependencies,
    MultivariateListingKey,
    build_multivariate_input_snapshot,
)
from portfell.multivariate_performance import build_multivariate_performance
from portfell.multivariate_quote_views import common_dates, first_price, last_price
from portfell.multivariate_refits import build_refitted_candidate_sets
from portfell.multivariate_risk_model import build_multivariate_risk_model
from portfell.multivariate_structure import build_multivariate_structure
from portfell.multivariate_validation import (
    build_candidate_scorecards,
    validate_candidate_stress,
    validate_candidates,
    walk_forward_validation_row,
)
from portfell.return_series import build_returns
from portfell.table_io import JsonRow


class MarketSourceMultivariateResearchService(MultivariateResearchService):
    """Run Multivariate only from the snapshot pinned by upstream research stages."""

    def __init__(
        self,
        market_data: MarketSourceResearchData,
        persistence: ResearchPersistencePort,
        research_repository: ResearchRunRepository,
        project_repository: ProjectRepository,
        selection_repository: SelectionRepository,
        run_repository: MultivariateRunRepository,
        metadata_rows: Callable[[], tuple[JsonRow, ...]],
        worker_count: Callable[[], int | None],
        workflow_projector: Callable[[str, str], object] | None,
    ) -> None:
        # The base class remains the explicit legacy/local compatibility surface until
        # the deletion wave. Production source resolution and computation are fully
        # overridden here and never call its ResearchDataPort paths.
        super().__init__(
            cast(ResearchDataPort, market_data),
            persistence,
            research_repository,
            project_repository,
            selection_repository,
            run_repository,
            metadata_rows,
            worker_count,
            workflow_projector,
        )
        self._market_data = market_data

    def _selection_for_bivariate(self, user_id: str, run_id: str) -> UnivariateSelection:
        bivariate = self._research.bivariate_run(run_id, user_id)
        matches = [
            selection
            for selection in self._research.univariate_selections(user_id)
            if _bivariate_market_snapshot_id(selection, bivariate.source_id) is not None
        ]
        if len(matches) != 1:
            raise HostedApplicationError(422, "bivariate_dependency_mismatch")
        return matches[0]

    def _compute(
        self,
        run: MultivariateRunRecord,
        *,
        executor: Executor,
        on_phase: Callable[[str, str, int], None],
    ) -> MultivariateRunRecord:
        selection = self._selection_for_bivariate(run.user_id, run.bivariate_run_id)
        bivariate = self._research.bivariate_run(run.bivariate_run_id, run.user_id)
        pinned_snapshot_id = _bivariate_market_snapshot_id(selection, bivariate.source_id)
        if pinned_snapshot_id is None:
            raise HostedApplicationError(422, "bivariate_dependency_mismatch")
        source_run = self._research.univariate_run(selection.source_run_id, run.user_id)
        metadata_selection = self._metadata_selection_for_project(run.user_id, run.project_id)
        market = self._read_market(selection.member_ids)
        if market.snapshot_id != pinned_snapshot_id:
            raise HostedApplicationError(409, "market_source_snapshot_changed")
        expected_source_id = univariate_source_id(
            metadata_selection.selection_id, market.snapshot_id
        )
        if source_run.source_id != expected_source_id:
            raise HostedApplicationError(422, "project_univariate_dependency_mismatch")
        return self._compute_from_snapshot(
            run,
            selection=selection,
            source_run_id=source_run.run_id,
            metadata_selection_id=metadata_selection.selection_id,
            market=market,
            executor=executor,
            on_phase=on_phase,
        )

    def _read_market(self, member_ids: tuple[str, ...]) -> MarketResearchSnapshot:
        try:
            return self._market_data.read(member_ids)
        except (MarketSourceError, MarketProjectionError) as error:
            raise HostedApplicationError(409, error.code) from error

    def _compute_from_snapshot(
        self,
        run: MultivariateRunRecord,
        *,
        selection: UnivariateSelection,
        source_run_id: str,
        metadata_selection_id: str,
        market: MarketResearchSnapshot,
        executor: Executor,
        on_phase: Callable[[str, str, int], None],
    ) -> MultivariateRunRecord:
        quotes = market.quotes
        dividends = market.dividends
        metadata = {
            (str(row.get("isin", "")), str(row.get("exchange", "")), str(row.get("code", ""))): row
            for row in self._metadata_rows()
        }
        selected: list[JsonRow] = []
        for row in selection.rows:
            key = (
                str(row.get("isin", "")),
                str(row.get("exchange", "")),
                str(row.get("code", "")),
            )
            selected.append({**metadata.get(key, {}), **row})
        returns = build_returns(quotes)
        keys = tuple(sorted(MultivariateListingKey.from_row(row) for row in selected))
        calendar_dates = common_dates(returns, keys)
        calendar_id = stable_hash(
            {"listing_keys": [key.as_tuple() for key in keys], "dates": calendar_dates}
        )
        dependencies = MultivariateInputDependencies(
            project_id=run.project_id,
            project_snapshot_id=run.logical_hash,
            metadata_selection_id=metadata_selection_id,
            univariate_run_id=source_run_id,
            univariate_selection_id=selection.selection_id,
            bivariate_run_id=run.bivariate_run_id,
            bivariate_status="complete",
            bivariate_listing_keys=keys,
            aligned_calendar_id=calendar_id,
            bivariate_aligned_calendar_id=calendar_id,
            date_start=calendar_dates[0] if calendar_dates else None,
            date_end=calendar_dates[-1] if calendar_dates else None,
            observation_count=len(calendar_dates),
            quote_artifact_ids={
                key: (f"quote:{market.snapshot_id}:{key.isin}:{key.exchange}:{key.code}")
                for key in keys
            },
            dividend_artifact_ids={
                key: (f"dividend:{market.snapshot_id}:{key.isin}:{key.exchange}:{key.code}")
                for key in keys
            },
        )
        snapshot = build_multivariate_input_snapshot(
            dependencies=dependencies, univariate_rows=selected
        )
        on_phase(run.run_id, "build_risk_model", 1)
        risk = build_multivariate_risk_model(snapshot=snapshot, return_rows=returns)
        on_phase(run.run_id, "build_structure", 2)
        structure = build_multivariate_structure(risk)
        on_phase(run.run_id, "build_income_evidence", 3)
        income = {
            key: build_income_evidence(
                listing=key,
                events=normalize_distribution_events(dividends, listing=key),
                period_end=snapshot.date_end or "1970-01-01",
                denominator_price=last_price(quotes, key),
                period_start=snapshot.date_start,
                start_price=first_price(quotes, key),
            )
            for key in keys
        }
        on_phase(run.run_id, "build_candidates", 4)
        candidates = build_candidate_set(
            snapshot=snapshot,
            risk_model=risk,
            return_rows=returns,
            income=income,
            executor=executor,
        )
        on_phase(run.run_id, "validate_candidates", 5)
        refitted_candidates = build_refitted_candidate_sets(
            executor=executor,
            candidates=candidates,
            snapshot=snapshot,
            return_rows=returns,
            income=income,
        )
        validation = validate_candidates(
            candidates=candidates,
            return_rows=returns,
            precomputed_candidates=refitted_candidates,
            risk_model_id=risk.risk_model_id,
        )
        scenarios = validate_candidate_stress(candidates=candidates, return_rows=returns)
        scorecards = build_candidate_scorecards(splits=validation, scenarios=scenarios)
        candidate_rows = tuple(
            {
                "candidate_id": item.candidate_id,
                "method": item.method,
                "baseline": item.baseline,
                "status": item.status,
                "reasons": list(item.reasons),
                "weights": [
                    {
                        "isin": key.isin,
                        "exchange": key.exchange,
                        "code": key.code,
                        "weight": weight,
                    }
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
            for item in candidates
        )
        risk_contributions = tuple(
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
        )
        income_rows = tuple(
            {
                "isin": key.isin,
                "exchange": key.exchange,
                "code": key.code,
                "currency": evidence.currency,
                "event_count": evidence.event_count,
                "observed_month_count": evidence.observed_month_count,
                "observed_payment_coverage": evidence.observed_payment_coverage,
                "gross_ttm_distribution_amount": evidence.gross_ttm_distribution_amount,
                "gross_ttm_distribution_yield": evidence.gross_ttm_distribution_yield,
                "mean_observed_monthly_distribution": evidence.mean_observed_monthly_distribution,
                "median_observed_monthly_distribution": (
                    evidence.median_observed_monthly_distribution
                ),
                "lower_percentile_monthly_distribution": (
                    evidence.lower_percentile_monthly_distribution
                ),
                "coefficient_of_variation": evidence.coefficient_of_variation,
                "cut_count": evidence.cut_count,
                "largest_cut": evidence.largest_cut,
                "longest_falling_sequence": evidence.longest_falling_sequence,
                "distribution_trend": evidence.distribution_trend,
                "price_return": evidence.price_return,
                "total_return": evidence.total_return,
                "distribution_to_total_return_gap": evidence.distribution_to_total_return_gap,
                "market_price_capital_change": evidence.market_price_capital_change,
                "availability_reasons": list(evidence.availability_reasons),
                "warnings": list(evidence.warnings),
            }
            for key, evidence in sorted(income.items())
        )
        components = tuple(
            {
                "component_id": loading.component_id,
                "isin": loading.listing.isin,
                "exchange": loading.listing.exchange,
                "code": loading.listing.code,
                "loading": loading.loading,
                "explained_variance": structure.explained_variance[
                    int(loading.component_id.rsplit(" ", 1)[-1]) - 1
                ],
                "cluster": dict(structure.cluster_by_listing).get(loading.listing),
            }
            for loading in structure.loadings
        )
        validation_rows = (
            tuple(walk_forward_validation_row(item) for item in validation)
            + tuple({"kind": "stress", **item.__dict__} for item in scenarios)
            + tuple({"kind": "scorecard", **item.__dict__} for item in scorecards)
        )
        summary = {
            "input_snapshot_id": snapshot.snapshot_id,
            "market_source_snapshot_id": market.snapshot_id,
            "risk_model_id": risk.risk_model_id,
            "candidate_etf_count": len(snapshot.listing_keys),
            "aligned_period": {
                "date_start": snapshot.date_start,
                "date_end": snapshot.date_end,
                "observation_count": snapshot.observation_count,
            },
            "availability_reasons": list(snapshot.availability_reasons),
        }
        artifacts = {
            "market_source": {
                "snapshot_id": market.snapshot_id,
                "split_event_count": len(market.splits),
                "split_policy": "lineage_only_no_return_adjustment",
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
            **build_income_artifacts(
                evidence_by_listing=income,
                dividend_rows=dividends,
                income_metrics=income_rows,
            ),
            "performance": build_multivariate_performance(
                candidates=candidates,
                return_rows=returns,
            ),
        }
        return replace(
            run,
            input_snapshot_id=snapshot.snapshot_id,
            status="complete",
            phase="complete",
            completed_units=6,
            summary=summary,
            structure=structure.summary(),
            candidates=candidate_rows,
            validation=validation_rows,
            artifacts=artifacts,
            components=components,
            risk_contributions=risk_contributions,
            income_evidence=income_rows,
            warnings=tuple(snapshot.availability_reasons),
        )


def _bivariate_market_snapshot_id(selection: UnivariateSelection, source_id: str) -> str | None:
    prefix = f"{bivariate_source_id(selection)}::"
    if not source_id.startswith(prefix):
        return None
    snapshot_id = source_id[len(prefix) :]
    if not snapshot_id or "::" in snapshot_id:
        return None
    return snapshot_id


__all__ = ["MarketSourceMultivariateResearchService"]
