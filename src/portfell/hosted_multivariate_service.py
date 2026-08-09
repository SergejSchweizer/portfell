"""Project-scoped Multivariate application service.

This service resolves an explicit completed Bivariate run and its dependency
closure. It deliberately does not call the generic analysis placeholder.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from time import time
from typing import Any

from portfell.gold import build_returns
from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_service_support import opaque_id, require_user_row, stable_hash
from portfell.hosted_api_state import HostedApiState, MultivariateRunRecord, SelectionRecord
from portfell.hosted_research_ports import ResearchDataPort, ResearchPersistencePort
from portfell.hosted_research_workflow import UnivariateSelection, bivariate_source_id
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
from portfell.multivariate_risk_model import build_multivariate_risk_model
from portfell.multivariate_structure import build_multivariate_structure
from portfell.multivariate_validation import (
    build_candidate_scorecards,
    validate_candidate_stress,
    validate_candidates,
)
from portfell.table_io import JsonRow


class MultivariateResearchService:
    """Run, persist, and expose Multivariate artifacts for one owned project."""

    def __init__(
        self,
        state: HostedApiState,
        data: ResearchDataPort,
        persistence: ResearchPersistencePort,
    ) -> None:
        self._state = state
        self._data = data
        self._persistence = persistence

    def start(
        self, user_id: str, project_id: str, bivariate_run_id: str, settings: JsonRow
    ) -> JsonRow:
        require_user_row(self._state.projects_by_id, project_id, user_id)
        bivariate = require_user_row(self._state.bivariate_runs_by_id, bivariate_run_id, user_id)
        if bivariate.status != "complete":
            raise HostedApplicationError(422, "bivariate_run_not_complete")
        self._metadata_selection_for_project(user_id, project_id)
        selection = self._selection_for_bivariate(user_id, bivariate_run_id)
        logical_hash = stable_hash(
            {
                "project_id": project_id,
                "bivariate_run_id": bivariate_run_id,
                "selection_id": selection.selection_id,
                "settings": settings,
            }
        )
        run_id = opaque_id("multivariate-run", f"{user_id}:{logical_hash}")
        existing = self._state.multivariate_runs_by_id.get(run_id)
        if existing is not None:
            return _run_row(existing)
        run = MultivariateRunRecord(
            run_id=run_id,
            user_id=user_id,
            project_id=project_id,
            bivariate_run_id=bivariate_run_id,
            input_snapshot_id="",
            logical_hash=logical_hash,
            status="running",
            phase="resolve_inputs",
            completed_units=0,
            total_units=6,
            started_at_epoch=time(),
            settings=dict(settings),
            summary={},
            structure={},
            candidates=(),
            validation=(),
        )
        self._state.multivariate_runs_by_id[run_id] = run
        self._state.current_multivariate_run_by_project[project_id] = run_id
        self._persistence.persist()
        return _run_row(run)

    def plan(
        self, user_id: str, project_id: str, bivariate_run_id: str, settings: JsonRow
    ) -> JsonRow:
        """Return a read-only, project-authorized execution plan before starting work."""
        require_user_row(self._state.projects_by_id, project_id, user_id)
        bivariate = require_user_row(self._state.bivariate_runs_by_id, bivariate_run_id, user_id)
        selection = self._selection_for_bivariate(user_id, bivariate_run_id)
        metadata = self._metadata_selection_for_project(user_id, project_id)
        reasons = [] if bivariate.status == "complete" else ["bivariate_run_not_complete"]
        return {
            "allowed": not reasons,
            "reasons": reasons,
            "project_id": project_id,
            "bivariate_run_id": bivariate_run_id,
            "metadata_selection_id": metadata.selection_id,
            "univariate_selection_id": selection.selection_id,
            "listing_count": len(selection.member_ids),
            "total_units": 6,
            "phases": [
                "resolve_inputs",
                "build_risk_model",
                "build_structure",
                "build_income_evidence",
                "build_candidates",
                "validate_candidates",
            ],
            "settings": dict(settings),
        }

    def complete(self, user_id: str, run_id: str) -> None:
        run = require_user_row(self._state.multivariate_runs_by_id, run_id, user_id)
        if run.status != "running":
            return
        try:
            completed = self._compute(run, on_phase=self._advance)
        except (HostedApplicationError, ValueError) as error:
            completed = replace(run, status="failed", phase="failed", failure_reason=str(error))
        self._state.multivariate_runs_by_id[run_id] = completed
        self._persistence.persist()

    def status(self, user_id: str, run_id: str) -> JsonRow:
        return _run_row(require_user_row(self._state.multivariate_runs_by_id, run_id, user_id))

    def summary(self, user_id: str, run_id: str) -> JsonRow:
        return dict(require_user_row(self._state.multivariate_runs_by_id, run_id, user_id).summary)

    def structure(self, user_id: str, run_id: str) -> JsonRow:
        return dict(
            require_user_row(self._state.multivariate_runs_by_id, run_id, user_id).structure
        )

    def candidates(self, user_id: str, run_id: str) -> JsonRow:
        run = require_user_row(self._state.multivariate_runs_by_id, run_id, user_id)
        return {"items": list(run.candidates)}

    def candidate_detail(self, user_id: str, run_id: str, candidate_id: str) -> JsonRow:
        run = require_user_row(self._state.multivariate_runs_by_id, run_id, user_id)
        candidate = next(
            (item for item in run.candidates if item.get("candidate_id") == candidate_id), None
        )
        if candidate is None:
            raise HostedApplicationError(404, "not_found")
        return dict(candidate)

    def risk_contributions(self, user_id: str, run_id: str, candidate_id: str | None) -> JsonRow:
        run = require_user_row(self._state.multivariate_runs_by_id, run_id, user_id)
        items = run.risk_contributions
        if candidate_id is not None:
            items = tuple(item for item in items if item.get("candidate_id") == candidate_id)
        return {"items": list(items)}

    def income_evidence(self, user_id: str, run_id: str) -> JsonRow:
        run = require_user_row(self._state.multivariate_runs_by_id, run_id, user_id)
        return {"items": list(run.income_evidence)}

    def components(self, user_id: str, run_id: str, limit: int, offset: int) -> JsonRow:
        run = require_user_row(self._state.multivariate_runs_by_id, run_id, user_id)
        safe_limit, safe_offset = max(1, min(limit, 100)), max(0, offset)
        return {
            "items": list(run.components[safe_offset : safe_offset + safe_limit]),
            "total": len(run.components),
            "limit": safe_limit,
            "offset": safe_offset,
        }

    def validation(self, user_id: str, run_id: str) -> JsonRow:
        run = require_user_row(self._state.multivariate_runs_by_id, run_id, user_id)
        return {"items": list(run.validation)}

    def artifacts(self, user_id: str, run_id: str) -> JsonRow:
        return dict(
            require_user_row(self._state.multivariate_runs_by_id, run_id, user_id).artifacts
        )

    def update_settings(
        self, user_id: str, run_id: str, selected_candidate_ids: tuple[str, ...]
    ) -> JsonRow:
        run = require_user_row(self._state.multivariate_runs_by_id, run_id, user_id)
        known_ids = {str(candidate.get("candidate_id")) for candidate in run.candidates}
        if (
            len(set(selected_candidate_ids)) != len(selected_candidate_ids)
            or not set(selected_candidate_ids) <= known_ids
        ):
            raise HostedApplicationError(422, "invalid_candidate_selection")
        updated = replace(
            run,
            settings={**run.settings, "selected_candidate_ids": list(selected_candidate_ids)},
        )
        self._state.multivariate_runs_by_id[run_id] = updated
        self._persistence.persist()
        return _run_row(updated)

    def _selection_for_bivariate(self, user_id: str, run_id: str) -> UnivariateSelection:
        bivariate = require_user_row(self._state.bivariate_runs_by_id, run_id, user_id)
        matches = [
            selection
            for selection in self._state.univariate_selections_by_id.values()
            if selection.user_id == user_id
            and bivariate_source_id(selection) == bivariate.source_id
        ]
        if len(matches) != 1:
            raise HostedApplicationError(422, "bivariate_dependency_mismatch")
        return matches[0]

    def _metadata_selection_for_project(self, user_id: str, project_id: str) -> SelectionRecord:
        selections = [
            selection
            for selection in self._state.selections_by_id.values()
            if selection.user_id == user_id and selection.project_id == project_id
        ]
        if len(selections) != 1:
            raise HostedApplicationError(422, "project_metadata_dependency_mismatch")
        return selections[0]

    def _advance(self, run_id: str, phase: str, completed_units: int) -> None:
        """Persist strictly monotonic phase progress for concurrent status polling."""

        current = self._state.multivariate_runs_by_id.get(run_id)
        if current is None or current.status != "running":
            return
        next_completed = max(current.completed_units, min(completed_units, current.total_units))
        advanced = replace(
            current,
            phase=phase if next_completed > current.completed_units else current.phase,
            completed_units=next_completed,
        )
        self._state.multivariate_runs_by_id[run_id] = advanced
        self._persistence.persist()

    def _compute(
        self,
        run: MultivariateRunRecord,
        *,
        on_phase: Callable[[str, str, int], None],
    ) -> MultivariateRunRecord:
        selection = self._selection_for_bivariate(run.user_id, run.bivariate_run_id)
        source_run = require_user_row(
            self._state.univariate_runs_by_id, selection.source_run_id, run.user_id
        )
        metadata_selection = self._metadata_selection_for_project(run.user_id, run.project_id)
        quote_run_id = self._state.quote_run_by_univariate_run_id.get(source_run.run_id, "")
        expected_source_id = stable_hash(
            {"selection_id": metadata_selection.selection_id, "quote_run_id": quote_run_id}
        )
        if source_run.source_id != expected_source_id:
            raise HostedApplicationError(422, "project_univariate_dependency_mismatch")
        quotes = self._state.quote_rows_by_run_id.get(quote_run_id) or self._data.selected_rows(
            selection.member_ids, dataset="quotes"
        )
        dividends = self._data.selected_rows(selection.member_ids, dataset="dividends")
        metadata = {
            (str(row.get("isin", "")), str(row.get("exchange", "")), str(row.get("code", ""))): row
            for row in self._state.all_isins_rows
        }
        selected: list[JsonRow] = []
        for row in selection.rows:
            key = (str(row.get("isin", "")), str(row.get("exchange", "")), str(row.get("code", "")))
            selected.append({**metadata.get(key, {}), **row})
        returns = build_returns(quotes)
        keys = tuple(sorted(MultivariateListingKey.from_row(row) for row in selected))
        common_dates = _common_dates(returns, keys)
        calendar_id = stable_hash(
            {"listing_keys": [key.as_tuple() for key in keys], "dates": common_dates}
        )
        dependencies = MultivariateInputDependencies(
            project_id=run.project_id,
            project_snapshot_id=run.logical_hash,
            metadata_selection_id=metadata_selection.selection_id,
            univariate_run_id=source_run.run_id,
            univariate_selection_id=selection.selection_id,
            bivariate_run_id=run.bivariate_run_id,
            bivariate_status="complete",
            bivariate_listing_keys=keys,
            aligned_calendar_id=calendar_id,
            bivariate_aligned_calendar_id=calendar_id,
            date_start=common_dates[0] if common_dates else None,
            date_end=common_dates[-1] if common_dates else None,
            observation_count=len(common_dates),
            quote_artifact_ids={
                key: f"quote:{quote_run_id}:{key.isin}:{key.exchange}:{key.code}" for key in keys
            },
            dividend_artifact_ids={
                key: f"dividend:{key.isin}:{key.exchange}:{key.code}" for key in keys
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
                denominator_price=_last_price(quotes, key),
                period_start=snapshot.date_start,
                start_price=_first_price(quotes, key),
            )
            for key in keys
        }
        on_phase(run.run_id, "build_candidates", 4)
        candidates = build_candidate_set(
            snapshot=snapshot, risk_model=risk, return_rows=returns, income=income
        )
        on_phase(run.run_id, "validate_candidates", 5)

        def refit_candidates(
            training_rows: Sequence[Mapping[str, Any]],
        ) -> tuple[PortfolioCandidate, ...]:
            training_risk = build_multivariate_risk_model(
                snapshot=snapshot, return_rows=training_rows
            )
            return build_candidate_set(
                snapshot=snapshot,
                risk_model=training_risk,
                return_rows=training_rows,
                income=income,
            )

        validation = validate_candidates(
            candidates=candidates,
            return_rows=returns,
            candidate_factory=refit_candidates,
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
                    {"isin": key.isin, "exchange": key.exchange, "code": key.code, "weight": weight}
                    for key, weight in item.weights
                ],
                "variance": item.variance,
                "volatility": item.volatility,
                "cvar": item.cvar,
                "gross_ttm_distribution_yield": item.gross_ttm_distribution_yield,
                "gross_monthly_distribution": item.gross_monthly_distribution,
                "total_return": item.total_return,
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
                "nav_erosion": evidence.nav_erosion,
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
            tuple({"kind": "walk_forward", **item.__dict__} for item in validation)
            + tuple({"kind": "stress", **item.__dict__} for item in scenarios)
            + tuple({"kind": "scorecard", **item.__dict__} for item in scorecards)
        )
        summary = {
            "input_snapshot_id": snapshot.snapshot_id,
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


def _run_row(run: MultivariateRunRecord) -> JsonRow:
    elapsed = max(0, int(time() - run.started_at_epoch)) if run.started_at_epoch else 0
    remaining_units = max(0, run.total_units - run.completed_units)
    per_unit = elapsed / run.completed_units if run.completed_units else 5.0
    return {
        "run_id": run.run_id,
        "project_id": run.project_id,
        "bivariate_run_id": run.bivariate_run_id,
        "input_snapshot_id": run.input_snapshot_id or None,
        "status": run.status,
        "phase": run.phase,
        "completed_units": run.completed_units,
        "total_units": run.total_units,
        "elapsed_seconds": elapsed,
        "estimated_remaining_seconds": 0
        if run.status == "complete"
        else max(1, int(remaining_units * per_unit)),
        "settings": dict(run.settings),
        "warnings": list(run.warnings),
        "failure_reason": run.failure_reason,
    }


def _common_dates(
    rows: tuple[JsonRow, ...] | list[JsonRow], keys: tuple[MultivariateListingKey, ...]
) -> tuple[str, ...]:
    by_key: dict[tuple[str, str, str], set[str]] = {}
    for row in rows:
        key = (str(row.get("isin", "")), str(row.get("exchange", "")), str(row.get("code", "")))
        by_key.setdefault(key, set()).add(str(row.get("date", "")))
    dates: set[str] = set(by_key.get(keys[0].as_tuple(), set())) if keys else set()
    for key in keys[1:]:
        dates &= by_key.get(key.as_tuple(), set())
    return tuple(sorted(date for date in dates if date))


def _last_price(
    rows: tuple[JsonRow, ...] | list[JsonRow], key: MultivariateListingKey
) -> float | None:
    matching = [row for row in rows if MultivariateListingKey.from_row(row) == key]
    if not matching:
        return None
    value = sorted(matching, key=lambda row: str(row.get("date", "")))[-1].get("adjusted_close")
    return float(value) if isinstance(value, int | float) and value > 0 else None


def _first_price(
    rows: tuple[JsonRow, ...] | list[JsonRow], key: MultivariateListingKey
) -> float | None:
    matching = [row for row in rows if MultivariateListingKey.from_row(row) == key]
    if not matching:
        return None
    value = sorted(matching, key=lambda row: str(row.get("date", "")))[0].get("adjusted_close")
    return float(value) if isinstance(value, int | float) and value > 0 else None
