"""Deterministic end-to-end dry-run pipeline."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from portfell.bronze import (
    build_bronze_plan,
    normalize_quote_rows,
    write_bronze_manifests,
)
from portfell.evaluation import write_evaluation_outputs, write_portfolio_evaluation
from portfell.gold import write_gold_inputs
from portfell.paths import LakePaths
from portfell.portfolio import PortfolioConstraints, write_optimized_weights
from portfell.silver import write_silver_quotes
from portfell.table_io import JsonRow, write_json, write_rows

SAMPLE_CANDIDATES: tuple[dict[str, str], ...] = (
    {
        "Code": "CSPX",
        "Exchange": "XETRA",
        "Type": "ETF",
        "Country": "Germany",
        "Currency": "EUR",
        "Isin": "IE00B5BMR087",
        "Name": "iShares Core S&P 500 UCITS ETF",
    },
    {
        "Code": "CSP1",
        "Exchange": "LSE",
        "Type": "ETF",
        "Country": "UK",
        "Currency": "GBX",
        "Isin": "IE00B5BMR087",
        "Name": "iShares Core S&P 500 UCITS ETF",
    },
    {
        "Code": "EQQQ",
        "Exchange": "XETRA",
        "Type": "ETF",
        "Country": "Germany",
        "Currency": "EUR",
        "Isin": "IE0032077012",
        "Name": "Invesco EQQQ NASDAQ-100 UCITS ETF",
    },
)


def _sample_quotes(symbol: str) -> list[dict[str, Any]]:
    base = 100.0 if symbol.startswith("CSPX") else 50.0
    return [
        {
            "date": "2026-07-10",
            "open": base,
            "high": base + 1,
            "low": base - 1,
            "close": base,
            "adjusted_close": base,
            "volume": 1000,
        },
        {
            "date": "2026-07-11",
            "open": base + 1,
            "high": base + 2,
            "low": base,
            "close": base + 1,
            "adjusted_close": base + 1,
            "volume": 1100,
        },
        {
            "date": "2026-07-12",
            "open": base + 2,
            "high": base + 3,
            "low": base + 1,
            "close": base + 3,
            "adjusted_close": base + 3,
            "volume": 1200,
        },
    ]


def run_dry_run(root: Path) -> JsonRow:
    paths = LakePaths(root=root)
    run_id = "dry-run-2026-07-12"
    search_run_id = "search-2026-07-12"
    now = datetime(2026, 7, 12, tzinfo=UTC)

    # The dry run is a deterministic analytical fixture, not discovery.  It
    # writes its explicit canonical universe directly so it cannot revive the
    # retired provider-search surface.
    canonical = _canonical_fixture(SAMPLE_CANDIDATES, search_run_id)
    write_rows(paths.canonical_universe(search_run_id), canonical)
    pointer = {
        "search_run_id": search_run_id,
        "canonical_universe_path": str(paths.canonical_universe(search_run_id)),
        "approved_at": now.isoformat(),
    }
    write_json(paths.current_universe(), pointer)
    plan = build_bronze_plan(
        canonical,
        run_id=run_id,
        start_date=date(2026, 7, 10),
        end_date=date(2026, 7, 12),
    )
    write_rows(paths.bronze_plan(run_id), plan)

    raw_by_symbol = {str(item["symbol"]): _sample_quotes(str(item["symbol"])) for item in plan}
    currencies = {str(row["isin"]): str(row["currency"]) for row in canonical}
    quotes = normalize_quote_rows(plan, raw_by_symbol, bronzed_at=now, currency_by_isin=currencies)
    write_silver_quotes(paths, quotes, concurrency=2)
    coverage = write_bronze_manifests(paths, run_id=run_id, quote_rows=quotes)
    returns, correlations, covariances, features = write_gold_inputs(paths, quotes)
    matrix, asset_metrics = write_evaluation_outputs(paths, evaluation_id="dry-run")
    portfolio_returns, drawdowns, portfolio_metrics = write_portfolio_evaluation(
        paths,
        evaluation_id="dry-run",
        portfolio_id="equal-weight",
    )
    optimized_weights = write_optimized_weights(
        paths,
        evaluation_id="dry-run",
        objective="minimum_variance",
        portfolio_id="minimum-variance",
        constraints=PortfolioConstraints(max_weight=1.0),
        grid_step=0.1,
    )
    summary: JsonRow = {
        "search_run_id": search_run_id,
        "bronze_run_id": run_id,
        "current_universe": pointer,
        "canonical_rows": len(canonical),
        "plan_rows": len(plan),
        "quote_rows": len(quotes),
        "coverage_rows": len(coverage),
        "return_rows": len(returns),
        "correlation_rows": len(correlations),
        "covariance_rows": len(covariances),
        "feature_rows": len(features),
        "return_matrix_rows": len(matrix),
        "asset_metric_rows": len(asset_metrics),
        "portfolio_return_rows": len(portfolio_returns),
        "drawdown_rows": len(drawdowns),
        "portfolio_metric_rows": len(portfolio_metrics),
        "optimized_weight_rows": len(optimized_weights),
    }
    write_json(paths.dry_run_summary(), summary)
    return summary


def _canonical_fixture(
    candidates: tuple[dict[str, str], ...], search_run_id: str
) -> list[JsonRow]:
    """Build the fixed dry-run universe without a discovery implementation."""

    selected: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        isin = candidate["Isin"]
        current = selected.get(isin)
        if current is None or (
            candidate["Exchange"].upper(), candidate["Code"]
        ) < (current["Exchange"].upper(), current["Code"]):
            selected[isin] = candidate
    return [
        {
            "search_run_id": search_run_id,
            "isin": isin,
            "code": row["Code"],
            "exchange": row["Exchange"],
            "instrument_type": row["Type"],
            "country": row["Country"],
            "currency": row["Currency"],
            "name": row["Name"],
            "normalized_name": " ".join(row["Name"].casefold().split()),
            "selection_reason": (
                "preferred_xetra" if row["Exchange"].upper() == "XETRA" else "fallback_exchange"
            ),
            "selected_for_bronze": True,
        }
        for isin, row in sorted(selected.items())
    ]
