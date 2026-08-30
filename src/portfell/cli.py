"""Command-line entry point for Portfell."""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Sequence
from pathlib import Path

from portfell.logging import get_logger, log_event, setup_logging
from portfell.univariate_statistics import DEFAULT_CONFIDENCE_LEVEL
from portfell.workflows import (
    run_bivariate_statistics_workflow,
    run_metadata_builder_workflow,
    run_multivariate_statistics_workflow,
    run_univariate_selection_workflow,
    run_univariate_statistics_workflow,
)

DEFAULT_ROOT = Path("lake")
LOGGER = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portfell portfolio data tooling.")
    parser.add_argument("--debug", action="store_true", help="Write verbose DEBUG logs.")
    subparsers = parser.add_subparsers(dest="command")
    metadata_builder = subparsers.add_parser(
        "metadata-builder",
        help="Create a metadata-based ISIN selection.",
    )
    metadata_builder.add_argument(
        "--debug",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Write verbose DEBUG logs.",
    )
    metadata_builder.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Lake root to read from.",
    )
    metadata_builder.add_argument(
        "--where",
        action="append",
        default=[],
        help="Conjunctive predicate such as country=DE, name~UCITS, or volume>=1000.",
    )
    metadata_builder.add_argument(
        "--name-contains",
        action="append",
        default=[],
        help="Case-insensitive text search in the instrument name. May be repeated.",
    )
    metadata_builder.add_argument("--selection-name", help="Optional stable human-readable name.")
    univariate = subparsers.add_parser(
        "univariate-statistics",
        help="Build reusable per-listing statistics from Silver quotes.",
    )
    univariate.add_argument(
        "--debug",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Write verbose DEBUG logs.",
    )
    univariate.add_argument("--root", default=str(DEFAULT_ROOT), help="Lake root to build from.")
    univariate.add_argument(
        "--selection-id",
        help="Metadata Builder selection id. Defaults to its latest persisted selection.",
    )
    univariate.add_argument(
        "--confidence-level",
        type=float,
        default=DEFAULT_CONFIDENCE_LEVEL,
        help="Tail-risk confidence level for VaR and expected shortfall.",
    )
    univariate.add_argument(
        "--concurrency",
        type=int,
        help="Worker process count. Defaults to all CPU cores visible to the system.",
    )
    univariate_selection = subparsers.add_parser(
        "univariate-selection",
        help="Create an ISIN selection from univariate statistics.",
    )
    univariate_selection.add_argument(
        "--debug",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Write verbose DEBUG logs.",
    )
    univariate_selection.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Lake root to read from.",
    )
    univariate_selection.add_argument(
        "--where",
        action="append",
        default=[],
        required=True,
        help="Conjunctive predicate such as max_drawdown>=-0.2 or sharpe_ratio>0.5.",
    )
    univariate_selection.add_argument(
        "--selection-name", help="Optional stable human-readable name."
    )
    bivariate = subparsers.add_parser(
        "bivariate-statistics",
        help="Build reusable pairwise statistics from Silver quotes.",
    )
    bivariate.add_argument(
        "--debug",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Write verbose DEBUG logs.",
    )
    bivariate.add_argument("--root", default=str(DEFAULT_ROOT), help="Lake root to build from.")
    bivariate.add_argument(
        "--selection-id",
        help=(
            "Optional metadata-builder or univariate selection id. "
            "Defaults to the latest univariate selection."
        ),
    )
    bivariate.add_argument(
        "--concurrency",
        type=int,
        help="Worker process count. Defaults to all CPU cores visible to the system.",
    )
    multivariate = subparsers.add_parser(
        "multivariate-statistics",
        help="Build portfolio statistics from the latest univariate selection.",
    )
    multivariate.add_argument(
        "--debug",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Write verbose DEBUG logs.",
    )
    multivariate.add_argument("--root", default=str(DEFAULT_ROOT), help="Lake root to build from.")
    multivariate.add_argument(
        "--selection-id",
        help="Univariate Statistics selection id. Defaults to its latest persisted selection.",
    )
    multivariate.add_argument(
        "--use-selection-statistics-cache",
        action="store_true",
        help=(
            "Use PR74 selection statistics views and generic Gold caches before "
            "running portfolio-level calculations."
        ),
    )
    multivariate.add_argument(
        "--evaluation-id",
        default="multivariate-latest",
        help="Stable evaluation id for generated portfolio artifacts.",
    )
    multivariate.add_argument(
        "--portfolio-id-prefix",
        default="multivariate",
        help="Prefix for generated portfolio ids.",
    )
    multivariate.add_argument(
        "--confidence-level",
        type=float,
        default=0.95,
        help="Tail-risk confidence level for asset and portfolio metrics.",
    )
    multivariate.add_argument(
        "--grid-step",
        type=float,
        default=0.1,
        help="Deterministic optimizer grid step. Defaults to 0.1.",
    )
    multivariate.add_argument(
        "--train-window",
        type=int,
        default=2,
        help="Walk-forward training window in common return rows.",
    )
    multivariate.add_argument(
        "--test-window",
        type=int,
        default=1,
        help="Walk-forward test window in common return rows.",
    )
    multivariate.add_argument(
        "--walk-forward-profile",
        choices=("development", "production"),
        default="development",
        help=(
            "Walk-forward policy: 'development' allows tiny fixture windows but is never "
            "production eligible; 'production' enforces minimum history, test window, "
            "completed-split, and concentration requirements."
        ),
    )
    multivariate.add_argument(
        "--rebalance-schedule",
        choices=("monthly", "quarterly", "annual", "threshold"),
        default="monthly",
        help="Rebalance simulation schedule.",
    )
    multivariate.add_argument(
        "--transaction-cost-rate",
        type=float,
        default=0.0,
        help="Transaction cost rate used in rebalance simulation.",
    )
    multivariate.add_argument(
        "--drift-threshold",
        type=float,
        help="Optional drift threshold for threshold rebalancing.",
    )
    multivariate.add_argument(
        "--min-weight",
        type=float,
        default=0.0,
        help="Minimum instrument weight for generated portfolios.",
    )
    multivariate.add_argument(
        "--max-weight",
        type=float,
        default=1.0,
        help="Maximum instrument weight for generated portfolios.",
    )
    multivariate.add_argument(
        "--concurrency",
        type=int,
        help=(
            "Worker process count for Gold input generation. "
            "Defaults to all CPU cores visible to the system."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the Portfell command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        print("portfell")
        return
    setup_logging(debug=getattr(args, "debug", False))
    log_event(
        LOGGER,
        logging.DEBUG,
        module="cli",
        event="args_parsed",
        fields={"command": args.command},
    )
    if args.command == "metadata-builder":
        summary = run_metadata_builder_workflow(
            root=Path(args.root),
            predicates=tuple(args.where),
            name_contains=tuple(args.name_contains),
            selection_name=args.selection_name,
        )
    elif args.command == "univariate-statistics":
        summary = run_univariate_statistics_workflow(
            root=Path(args.root),
            selection_id=args.selection_id,
            confidence_level=args.confidence_level,
            concurrency=args.concurrency,
        )
    elif args.command == "univariate-selection":
        summary = run_univariate_selection_workflow(
            root=Path(args.root),
            predicates=tuple(args.where),
            selection_name=args.selection_name,
        )
    elif args.command == "bivariate-statistics":
        summary = run_bivariate_statistics_workflow(
            root=Path(args.root),
            selection_id=args.selection_id,
            concurrency=args.concurrency,
        )
    elif args.command == "multivariate-statistics":
        summary = run_multivariate_statistics_workflow(
            root=Path(args.root),
            selection_id=args.selection_id,
            evaluation_id=args.evaluation_id,
            portfolio_id_prefix=args.portfolio_id_prefix,
            confidence_level=args.confidence_level,
            grid_step=args.grid_step,
            train_window=args.train_window,
            test_window=args.test_window,
            walk_forward_profile=args.walk_forward_profile,
            rebalance_schedule=args.rebalance_schedule,
            transaction_cost_rate=args.transaction_cost_rate,
            drift_threshold=args.drift_threshold,
            min_weight=args.min_weight,
            max_weight=args.max_weight,
            concurrency=args.concurrency,
            use_selection_statistics_cache=args.use_selection_statistics_cache,
        )
    else:
        print("portfell")
        return
    print(json.dumps(summary, sort_keys=True))
