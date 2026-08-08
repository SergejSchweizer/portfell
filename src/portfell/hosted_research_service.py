"""Research and analysis application service."""

from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from importlib import import_module
from math import sqrt
from pathlib import Path
from statistics import median
from typing import Any

from portfell.gold import build_returns
from portfell.gold_pair_stats import sample_covariance
from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_serializers import (
    analysis_row,
    filter_selection_row,
    research_run_row,
    univariate_metric_rows,
)
from portfell.hosted_api_service_support import (
    audit,
    idempotent_response,
    opaque_id,
    remember_idempotency,
    require_user_row,
    stable_hash,
)
from portfell.hosted_api_state import AnalysisRecord, HostedApiState, SelectionRecord
from portfell.hosted_research_workflow import (
    FilterSelection,
    HostedResearchError,
    ResearchRun,
    create_bivariate_run,
    create_filter_selection,
    create_full_univariate_selection,
    create_univariate_run,
    create_univariate_run_from_statistics,
    page_rows,
    pair_plan,
)
from portfell.portfolio_parts.solvers import solve_minimum_variance
from portfell.table_io import JsonRow, read_rows, write_rows
from portfell.univariate_statistics import (
    annual_dividend_features,
    build_univariate_statistics,
    distribution_features,
    index_distribution_events,
)


class ResearchService:
    """Own univariate, filter, bivariate, and analysis transitions."""

    def __init__(self, state: HostedApiState) -> None:
        self.state = state

    def start_univariate(self, user_id: str, selection_id: str, quote_run_id: str) -> JsonRow:
        selection = require_user_row(self.state.selections_by_id, selection_id, user_id)
        quote_run = require_user_row(self.state.downloads_by_id, quote_run_id, user_id)
        if quote_run.status != "succeeded":
            raise HostedApplicationError(409, "quote_run_incomplete")
        source_id = stable_hash(
            {"selection_id": selection.selection_id, "quote_run_id": quote_run.download_run_id}
        )
        run_id = opaque_id("univariate-run", f"{user_id}:{source_id}")
        existing = self.state.univariate_runs_by_id.get(run_id)
        if existing is not None:
            if existing.status != "failed":
                return research_run_row(existing)
            self.state.univariate_runs_by_id.pop(run_id, None)
            self.state.quote_run_by_univariate_run_id.pop(run_id, None)
        run = ResearchRun(
            run_id=run_id,
            user_id=user_id,
            source_id=source_id,
            status="running",
            rows=(),
            total=len(selection.member_ids),
            completed=0,
        )
        self.state.univariate_runs_by_id[run.run_id] = run
        self.state.quote_run_by_univariate_run_id[run.run_id] = quote_run.download_run_id
        audit(self.state, user_id, "univariate_statistics.start")
        return research_run_row(run)

    def complete_univariate(self, user_id: str, selection_id: str, quote_run_id: str) -> None:
        """Compute a previously created run outside the request-response lifecycle."""

        selection = require_user_row(self.state.selections_by_id, selection_id, user_id)
        quote_run = require_user_row(self.state.downloads_by_id, quote_run_id, user_id)
        source_id = stable_hash(
            {"selection_id": selection.selection_id, "quote_run_id": quote_run.download_run_id}
        )
        run_id = opaque_id("univariate-run", f"{user_id}:{source_id}")
        run = require_user_row(self.state.univariate_runs_by_id, run_id, user_id)
        if run.status != "running":
            return
        quote_rows = self.state.quote_rows_by_run_id.get(quote_run.download_run_id, ())
        if quote_rows:
            computed = create_univariate_run(
                user_id=user_id,
                selection_id=selection.selection_id,
                quote_run_id=quote_run.download_run_id,
                quote_rows=quote_rows,
                dividend_rows=_read_scoped_lake_rows(selection, dataset="dividends"),
            )
        else:
            rows = _build_scoped_univariate_rows(
                selection,
                on_progress=lambda completed: self._update_univariate_progress(run_id, completed),
            )
            if not rows:
                self.state.univariate_runs_by_id[run_id] = replace(
                    run, status="failed", failed=run.total
                )
                audit(self.state, user_id, "univariate_statistics.failed")
                return
            computed = create_univariate_run_from_statistics(
                user_id=user_id,
                selection_id=selection.selection_id,
                quote_run_id=quote_run.download_run_id,
                rows=rows,
            )
        completed_run = replace(
            computed,
            run_id=run_id,
            total=run.total,
            completed=run.total,
        )
        self.state.univariate_runs_by_id[run_id] = completed_run
        full_selection = create_full_univariate_selection(user_id=user_id, run=completed_run)
        self.state.filter_selections_by_id.setdefault(full_selection.selection_id, full_selection)
        self.state.current_filter_selection_by_user[user_id] = full_selection.selection_id
        audit(self.state, user_id, "univariate_statistics.compute")

    def _update_univariate_progress(self, run_id: str, completed: int) -> None:
        run = self.state.univariate_runs_by_id.get(run_id)
        if run is not None and run.status == "running":
            self.state.univariate_runs_by_id[run_id] = replace(
                run, completed=min(completed, run.total)
            )

    def univariate_status(self, user_id: str, run_id: str) -> JsonRow:
        return research_run_row(require_user_row(self.state.univariate_runs_by_id, run_id, user_id))

    def univariate_results(self, user_id: str, run_id: str, limit: int, offset: int) -> JsonRow:
        run = require_user_row(self.state.univariate_runs_by_id, run_id, user_id)
        return page_rows(run.rows, limit=limit, offset=offset)

    def filter_metrics(self) -> JsonRow:
        return {"items": univariate_metric_rows()}

    def apply_filter(self, user_id: str, source_run_id: str, predicates: list[JsonRow]) -> JsonRow:
        run = require_user_row(self.state.univariate_runs_by_id, source_run_id, user_id)
        try:
            selection = create_filter_selection(user_id=user_id, run=run, predicate_rows=predicates)
        except HostedResearchError as error:
            raise HostedApplicationError(422, str(error)) from error
        self.state.filter_selections_by_id.setdefault(selection.selection_id, selection)
        self.state.current_filter_selection_by_user[user_id] = selection.selection_id
        return filter_selection_row(self.state.filter_selections_by_id[selection.selection_id])

    def filter_results(self, user_id: str, selection_id: str, limit: int, offset: int) -> JsonRow:
        selection = require_user_row(self.state.filter_selections_by_id, selection_id, user_id)
        return page_rows(selection.rows, limit=limit, offset=offset)

    def bivariate_plan(self, user_id: str, selection_id: str) -> JsonRow:
        selection = require_user_row(self.state.filter_selections_by_id, selection_id, user_id)
        return pair_plan(selection)

    def start_bivariate(self, user_id: str, selection_id: str) -> JsonRow:
        selection = require_user_row(self.state.filter_selections_by_id, selection_id, user_id)
        plan = pair_plan(selection)
        if not plan["allowed"]:
            raise HostedApplicationError(422, "pair_plan_not_runnable")
        source = stable_hash(
            {"selection_id": selection.selection_id, "members": list(selection.member_ids)}
        )
        run_id = opaque_id("bivariate-run", f"{user_id}:{source}")
        existing = self.state.bivariate_runs_by_id.get(run_id)
        if existing is not None and existing.status != "failed":
            return research_run_row(existing)
        run = ResearchRun(
            run_id=run_id,
            user_id=user_id,
            source_id=source,
            status="running",
            rows=(),
            total=int(plan["theoretical_pair_count"]),
            completed=0,
        )
        self.state.bivariate_runs_by_id[run_id] = run
        audit(self.state, user_id, "bivariate_statistics.start")
        return research_run_row(run)

    def complete_bivariate(self, user_id: str, selection_id: str) -> None:
        """Compute every bivariate statistic in the background using all CPU cores."""

        selection = require_user_row(self.state.filter_selections_by_id, selection_id, user_id)
        source = stable_hash(
            {"selection_id": selection.selection_id, "members": list(selection.member_ids)}
        )
        run_id = opaque_id("bivariate-run", f"{user_id}:{source}")
        run = require_user_row(self.state.bivariate_runs_by_id, run_id, user_id)
        if run.status != "running":
            return
        source_run = require_user_row(
            self.state.univariate_runs_by_id, selection.source_run_id, user_id
        )
        quote_run_id = self.state.quote_run_by_univariate_run_id.get(source_run.run_id, "")
        quote_rows = self.state.quote_rows_by_run_id.get(quote_run_id, ())
        # Hosted downloads deliberately avoid retaining every quote row in process
        # memory. The Silver lake is the durable source of truth, so restore the
        # selected rows from it after a container restart (or memory-safe download).
        if not quote_rows:
            quote_rows = _read_scoped_lake_rows(selection, dataset="quotes")
        if not quote_rows:
            self.state.bivariate_runs_by_id[run_id] = replace(
                run, status="failed", failed=run.total
            )
            return

        def update_progress(completed: int, total: int) -> None:
            active = self.state.bivariate_runs_by_id.get(run_id)
            if active is not None and active.status == "running":
                self.state.bivariate_runs_by_id[run_id] = replace(
                    active, completed=min(completed, total), total=total
                )

        try:
            computed = create_bivariate_run(
                user_id=user_id,
                selection=selection,
                quote_rows=quote_rows,
                on_progress=update_progress,
            )
        except HostedResearchError:
            self.state.bivariate_runs_by_id[run_id] = replace(
                run, status="failed", failed=run.total
            )
            audit(self.state, user_id, "bivariate_statistics.failed")
            return
        self.state.bivariate_runs_by_id[run_id] = replace(
            computed, run_id=run_id, total=computed.total, completed=computed.total
        )
        audit(self.state, user_id, "bivariate_statistics.complete")

    def bivariate_status(self, user_id: str, run_id: str) -> JsonRow:
        return research_run_row(require_user_row(self.state.bivariate_runs_by_id, run_id, user_id))

    def bivariate_results(self, user_id: str, run_id: str, limit: int, offset: int) -> JsonRow:
        run = require_user_row(self.state.bivariate_runs_by_id, run_id, user_id)
        return page_rows(run.rows, limit=limit, offset=offset)

    def bivariate_summary(self, user_id: str, run_id: str) -> JsonRow:
        """Aggregate all pair rows for the bivariate-statistics cards."""

        run = require_user_row(self.state.bivariate_runs_by_id, run_id, user_id)
        metric_names = (
            "pearson_correlation",
            "spearman_correlation",
            "downside_correlation",
            "lower_tail_dependence",
            "tail_coexceedance_rate",
            "rolling_correlation_stability",
            "drawdown_overlap_rate",
        )
        return {
            "pair_count": len(run.rows),
            "observation_count": round(
                sum(int(row.get("n_observations", 0)) for row in run.rows) / len(run.rows)
            )
            if run.rows
            else 0,
            "metrics": {
                name: _bivariate_metric_summary(
                    [float(row[name]) for row in run.rows if row.get(name) is not None]
                )
                for name in metric_names
            },
        }

    def bivariate_correlation_matrix(
        self, user_id: str, run_id: str, metric: str
    ) -> JsonRow:
        """Expose the upper triangle of one correlation matrix from pair results."""

        run = require_user_row(self.state.bivariate_runs_by_id, run_id, user_id)
        metric_key = f"{metric}_correlation"
        listings = tuple(
            sorted(
                {
                    (
                        str(row[side + "_isin"]),
                        str(row[side + "_exchange"]),
                        str(row[side + "_code"]),
                    )
                    for row in run.rows
                    for side in ("left", "right")
                }
            )
        )
        index = {listing: position for position, listing in enumerate(listings)}
        values_by_pair = {
            (
                index[(str(row["left_isin"]), str(row["left_exchange"]), str(row["left_code"]))],
                index[(str(row["right_isin"]), str(row["right_exchange"]), str(row["right_code"]))],
            ): float(row.get(metric_key, 0.0))
            for row in run.rows
        }
        return {
            "labels": [
                {"isin": isin, "exchange": exchange, "code": code, "label": f"{code}.{exchange}"}
                for isin, exchange, code in listings
            ],
            "values": [
                [
                    values_by_pair.get((row, column)) if column > row else None
                    for column in range(len(listings))
                ]
                for row in range(len(listings))
            ],
            "observation_count": round(
                sum(int(row.get("n_observations", 0)) for row in run.rows) / len(run.rows)
            )
            if run.rows
            else 0,
        }

    def bivariate_covariance_matrix(self, user_id: str, run_id: str) -> JsonRow:
        """Build a common-date daily log-return covariance matrix for one run."""

        run = require_user_row(self.state.bivariate_runs_by_id, run_id, user_id)
        selection = next(
            (
                item
                for item in self.state.filter_selections_by_id.values()
                if item.user_id == user_id
                and stable_hash(
                    {"selection_id": item.selection_id, "members": list(item.member_ids)}
                )
                == run.source_id
            ),
            None,
        )
        if selection is None:
            raise HostedApplicationError(404, "not_found")
        quote_run_id = self.state.quote_run_by_univariate_run_id.get(selection.source_run_id, "")
        quotes = self.state.quote_rows_by_run_id.get(quote_run_id, ())
        if not quotes:
            quotes = _read_scoped_lake_rows(selection, dataset="quotes")
        members = set(selection.member_ids)
        values_by_listing: dict[tuple[str, str, str], dict[str, float]] = {}
        scoped_quotes = tuple(
            row
            for row in quotes
            if f"{row.get('isin', '')}:{row.get('exchange', '')}:{row.get('code', '')}" in members
        )
        for row in build_returns(scoped_quotes):
            key = (str(row["isin"]), str(row["exchange"]), str(row["code"]))
            values_by_listing.setdefault(key, {})[str(row["date"])] = float(row["return"])
        listings = tuple(sorted(values_by_listing))
        common_dates: set[str] = set(values_by_listing[listings[0]]) if listings else set()
        for listing in listings[1:]:
            common_dates.intersection_update(values_by_listing[listing])
        dates: tuple[str, ...] = tuple(sorted(common_dates))
        values: list[tuple[float, ...]] = [
            tuple(values_by_listing[listing][date] for date in dates) for listing in listings
        ]
        covariance_values: list[list[float]] = [[0.0] * len(values) for _ in values]
        matrix_values: list[list[float | None]] = []
        for row_index, left in enumerate(values):
            display_row: list[float | None] = []
            for column_index, right in enumerate(values):
                if column_index < row_index:
                    covariance = covariance_values[column_index][row_index]
                else:
                    covariance = sample_covariance(left, right)
                    covariance_values[row_index][column_index] = covariance
                    covariance_values[column_index][row_index] = covariance
                display_row.append(None if column_index <= row_index else covariance)
            matrix_values.append(display_row)
        diagnostics = _covariance_diagnostics(listings, covariance_values, len(dates))
        return {
            "labels": [
                {"isin": isin, "exchange": exchange, "code": code, "label": f"{code}.{exchange}"}
                for isin, exchange, code in listings
            ],
            # Covariance is symmetric, so expose only the upper triangle.
            # Diagonal self-relations are kept only for portfolio diagnostics.
            "values": matrix_values,
            "observation_count": len(dates),
            "diagnostics": diagnostics,
        }

    def create_analysis(
        self,
        user_id: str,
        project_id: str,
        selection_id: str,
        settings: JsonRow,
        idempotency_key: str | None,
    ) -> JsonRow:
        selection = require_user_row(self.state.selections_by_id, selection_id, user_id)
        require_user_row(self.state.projects_by_id, project_id, user_id)
        logical_hash = stable_hash(
            {
                "selection_id": selection.selection_id,
                "member_ids": list(selection.member_ids),
                "settings": settings,
            }
        )
        cached = idempotent_response(
            self.state,
            user_id=user_id,
            operation="analysis",
            idempotency_key=idempotency_key,
        )
        if cached is not None:
            return {**analysis_row(self.state.analyses_by_id[cached]), "cache_hit": True}
        run_id = opaque_id("analysis", f"{user_id}:{logical_hash}")
        count = len(selection.member_ids)
        analysis = AnalysisRecord(
            run_id=run_id,
            user_id=user_id,
            project_id=project_id,
            selection_id=selection.selection_id,
            logical_hash=logical_hash,
            status="succeeded",
            metrics=({"name": "selection_size", "value": count},),
            returns=tuple(
                {"member_id": member_id, "return": 0.0} for member_id in selection.member_ids
            ),
            weights=tuple(
                {"member_id": member_id, "weight": 1 / count} for member_id in selection.member_ids
            ),
            report={"summary": "deterministic hosted analysis placeholder"},
        )
        self.state.analyses_by_id[run_id] = analysis
        remember_idempotency(self.state, user_id, "analysis", idempotency_key, run_id)
        audit(self.state, user_id, "analysis.create")
        return {**analysis_row(analysis), "cache_hit": False}

    def analysis(self, user_id: str, run_id: str) -> AnalysisRecord:
        return require_user_row(self.state.analyses_by_id, run_id, user_id)

    def analysis_status(self, user_id: str, run_id: str) -> JsonRow:
        return analysis_row(self.analysis(user_id, run_id))

    def analysis_metrics(self, user_id: str, run_id: str) -> JsonRow:
        return {"items": list(self.analysis(user_id, run_id).metrics)}

    def analysis_returns(self, user_id: str, run_id: str) -> JsonRow:
        return {"items": list(self.analysis(user_id, run_id).returns)}

    def analysis_weights(self, user_id: str, run_id: str) -> JsonRow:
        return {"items": list(self.analysis(user_id, run_id).weights)}

    def analysis_report(self, user_id: str, run_id: str) -> JsonRow:
        return self.analysis(user_id, run_id).report


def _bivariate_metric_summary(values: list[float]) -> JsonRow:
    """Compact distribution data for a pairwise metric card."""

    if not values:
        return {"mean": None, "median": None, "minimum": None, "maximum": None, "histogram": []}
    low, high = min(values), max(values)
    bins = 8
    counts = [0] * bins
    if high == low:
        counts[0] = len(values)
        edges = [low, high]
    else:
        width = (high - low) / bins
        edges = [low + width * index for index in range(bins + 1)]
        for value in values:
            counts[min(bins - 1, int((value - low) / width))] += 1
    return {
        "mean": sum(values) / len(values),
        "median": median(values),
        "minimum": low,
        "maximum": high,
        "histogram": [
            {
                "lower": edges[index] if len(edges) > 2 else low,
                "upper": edges[index + 1] if len(edges) > 2 else high,
                "count": count,
            }
            for index, count in enumerate(counts)
            if count > 0
        ],
    }


def _covariance_diagnostics(
    listings: tuple[tuple[str, str, str], ...],
    covariance: list[list[float]],
    observation_count: int,
) -> JsonRow:
    """Return portfolio-relevant facts from one dense covariance estimate."""

    count = len(listings)
    if count == 0:
        return {"listing_count": 0, "pair_count": 0, "observation_count": observation_count}
    pairs = [covariance[left][right] for left in range(count) for right in range(left + 1, count)]
    correlations = [
        value / sqrt(covariance[left][left] * covariance[right][right])
        for left in range(count)
        for right, value in enumerate(covariance[left])
        if right > left and covariance[left][left] > 0 and covariance[right][right] > 0
    ]
    weights = [1.0 / count] * count
    covariance_weights = [
        sum(value * weight for value, weight in zip(row, weights, strict=True))
        for row in covariance
    ]
    equal_variance = sum(
        weight * value for weight, value in zip(weights, covariance_weights, strict=True)
    )
    equal_volatility = sqrt(max(0.0, equal_variance))
    weighted_volatility = sum(
        weight * sqrt(max(0.0, covariance[index][index])) for index, weight in enumerate(weights)
    )
    risk_contributions = [
        weight * value for weight, value in zip(weights, covariance_weights, strict=True)
    ]
    risk_shares = (
        [value / equal_variance for value in risk_contributions] if equal_variance > 0 else []
    )
    effective_bets = 1.0 / sum(share * share for share in risk_shares) if risk_shares else None
    covariance_map = {
        (left, right): covariance[left_index][right_index]
        for left_index, left in enumerate(listings)
        for right_index, right in enumerate(listings)
    }
    minimum_variance = solve_minimum_variance(
        listings, covariance_map, min_weight=0.0, max_weight=1.0
    )
    return {
        "listing_count": count,
        "pair_count": len(pairs),
        "observation_count": observation_count,
        "average_pairwise_covariance": (sum(pairs) / len(pairs)) if pairs else None,
        "average_pairwise_correlation": (sum(correlations) / len(correlations))
        if correlations
        else None,
        "equal_weight_volatility": equal_volatility,
        "minimum_variance_volatility": sqrt(max(0.0, minimum_variance.objective_value)),
        "diversification_ratio": (weighted_volatility / equal_volatility)
        if equal_volatility
        else None,
        "effective_number_of_bets": effective_bets,
        "largest_equal_weight_risk_contribution": max(risk_shares) if risk_shares else None,
    }


def _read_scoped_lake_rows(
    selection: SelectionRecord | FilterSelection, *, dataset: str
) -> tuple[JsonRow, ...]:
    """Read durable selected quote or dividend rows after an API restart."""

    paths = _lake_paths()
    rows: list[JsonRow] = []
    for member_id in selection.member_ids:
        isin, exchange, code = member_id.split(":", 2)
        source_paths = (
            (paths.silver_quote_file(exchange, isin),)
            if dataset == "quotes"
            else tuple((paths.bronze / dataset / exchange).glob(f"*/{isin}.parquet"))
        )
        for path in source_paths:
            rows.extend(row for row in read_rows(path) if str(row.get("code", "")) == code)
    return tuple(rows)


def _build_scoped_univariate_rows(
    selection: SelectionRecord, *, on_progress: Callable[[int], None] | None = None
) -> tuple[JsonRow, ...]:
    """Recompute selected listings one at a time, avoiding a multi-million-row heap."""

    rows: list[JsonRow] = []
    with ProcessPoolExecutor(max_workers=os.cpu_count() or 1) as executor:
        for index, row in enumerate(
            executor.map(_build_scoped_univariate_listing, selection.member_ids), start=1
        ):
            if row is not None:
                rows.append(row)
            if on_progress is not None:
                on_progress(index)
    return tuple(rows)


def _build_scoped_univariate_listing(member_id: str) -> JsonRow | None:
    """Use one worker process per selected listing, bounded by available CPU cores."""

    paths = _lake_paths()
    isin, exchange, code = member_id.split(":", 2)
    dividend_rows = [
        row
        for path in (paths.bronze / "dividends" / exchange).glob(f"*/{isin}.parquet")
        for row in read_rows(path)
        if str(row.get("code", "")) == code
    ]
    cached_rows = read_rows(paths.gold_univariate_statistics(exchange, isin))
    if len(cached_rows) == 1 and str(cached_rows[0].get("code", "")) == code:
        row = dict(cached_rows[0])
        dates = index_distribution_events(dividend_rows).get((isin, exchange, code), ())
        distribution = distribution_features(dates)
        annual_dividend = annual_dividend_features(
            dividend_rows, str(row["last_quote_date"]), float(row["end_adjusted_close"])
        )
        if any(row.get(key) != value for key, value in {**distribution, **annual_dividend}.items()):
            row.update(distribution)
            row.update(annual_dividend)
            write_rows(paths.gold_univariate_statistics(exchange, isin), [row])
        return row
    quote_rows = [
        row
        for row in read_rows(paths.silver_quote_file(exchange, isin))
        if str(row.get("code", "")) == code
    ]
    if not quote_rows:
        return None
    return build_univariate_statistics(quote_rows, dividend_rows=dividend_rows, concurrency=None)[0]


def _lake_paths() -> Any:
    """Resolve the local data-lake adapter without coupling service imports to storage."""

    path_type = import_module("portfell.paths").LakePaths
    return path_type(root=Path(os.environ.get("PORTFELL_LAKE_ROOT", "lake")))
