"""Deterministic in-memory service fixture for Dash browser parity QA only."""

from __future__ import annotations

from dataclasses import dataclass


class FixturePublicError(RuntimeError):
    """Typed fixture failure carrying a public code and deliberately sensitive detail."""

    code = "fixture_univariate_failed"

    def __init__(self) -> None:
        super().__init__("internal fixture detail postgres://fixture-secret@localhost")


@dataclass
class DashParityFixtureService:
    level: int = 0
    universe_revision: int = 1
    fail_next_univariate: bool = False
    failure_count: int = 0

    def metadata_options(self) -> dict[str, object]:
        return {
            "exchange": ["XETRA"],
            "instrument_type": ["ETF"],
            "country": ["DE"],
            "currency": ["EUR"],
            "active_listing_count": 2,
        }

    def active_listings(self, **filters: object) -> tuple[dict[str, object], ...]:
        exchange = filters.get("exchange")
        instrument_type = filters.get("instrument_type")
        country = filters.get("country")
        currency = filters.get("currency")
        rows = (
            {
                "isin": "DE000TEST01",
                "exchange": "XETRA",
                "code": "AAA",
                "name": "Fixture ETF A",
                "instrument_type": "ETF",
                "country": "DE",
                "currency": "EUR",
            },
            {
                "isin": "DE000TEST02",
                "exchange": "XETRA",
                "code": "BBB",
                "name": "Fixture ETF B",
                "instrument_type": "ETF",
                "country": "DE",
                "currency": "EUR",
            },
        )
        expected = {
            "exchange": exchange,
            "instrument_type": instrument_type,
            "country": country,
            "currency": currency,
        }
        return tuple(
            row
            for row in rows
            if all(value in {None, row[name]} for name, value in expected.items())
        )

    def metadata_history(self) -> tuple[dict[str, object], ...]:
        return () if self.level < 1 else (self._universe(),)

    def create_metadata_universe(self, **filters: object) -> object:
        if not self.active_listings(**filters):
            raise RuntimeError("fixture_universe_empty")
        self.level = max(self.level, 1)
        return self._universe()

    def run_univariate(self, universe_id: str) -> dict[str, object]:
        assert universe_id == self._universe_id()
        if self.fail_next_univariate:
            self.fail_next_univariate = False
            self.failure_count += 1
            raise FixturePublicError()
        self.level = max(self.level, 2)
        return self._univariate_run()

    def create_univariate_selection(self, run_id: str, *, predicates=None) -> object:
        assert run_id == "fixture-univariate-run"
        assert predicates is None
        self.level = max(self.level, 3)
        return self._selection()

    def run_bivariate(self, selection_id: str) -> dict[str, object]:
        assert selection_id == "fixture-selection-1"
        self.level = max(self.level, 4)
        return self._bivariate_run()

    def run_multivariate(
        self,
        *,
        selection_id: str,
        bivariate_run_id: str,
        objective: str = "return_risk",
    ) -> dict[str, object]:
        assert selection_id == "fixture-selection-1"
        assert bivariate_run_id == "fixture-bivariate-run"
        assert objective in {"return_risk", "return_drawdown", "minimum_risk"}
        self.level = max(self.level, 5)
        return self._multivariate_run(objective)

    def advance_universe_revision(self) -> None:
        """Publish a new upstream revision and remove stale descendants from current projection."""
        self.universe_revision += 1
        self.level = 1

    def workflow_state(self) -> dict[str, object]:
        universe = self._universe() if self.level >= 1 else None
        univariate = self._univariate_run() if self.level >= 2 else None
        selection = self._selection() if self.level >= 3 else None
        bivariate = self._bivariate_run() if self.level >= 4 else None
        multivariate = self._multivariate_run("return_risk") if self.level >= 5 else None
        return {
            "workspace_id": "default",
            "metadata_universe": universe,
            "univariate_selection": selection,
            "stages": {
                "univariate": univariate,
                "bivariate": bivariate,
                "multivariate": multivariate,
            },
        }

    def run_detail(self, run_id: str) -> dict[str, object]:
        if run_id == "fixture-univariate-run":
            return {
                **self._univariate_run(),
                "artifacts": {
                    "univariate_rows": {
                        "items": [
                            {
                                "isin": "DE000TEST01",
                                "exchange": "XETRA",
                                "code": "AAA",
                                "annualized_return": 0.10,
                                "annualized_volatility": 0.15,
                                "max_drawdown": -0.12,
                                "sharpe_ratio": 0.67,
                                "sortino_ratio": 0.91,
                                "annual_dividend_yield": 0.025,
                                "availability_reason": "ok",
                            },
                            {
                                "isin": "DE000TEST02",
                                "exchange": "XETRA",
                                "code": "BBB",
                                "annualized_return": 0.08,
                                "annualized_volatility": 0.11,
                                "max_drawdown": -0.09,
                                "sharpe_ratio": 0.73,
                                "sortino_ratio": 0.98,
                                "annual_dividend_yield": 0.018,
                                "availability_reason": "ok",
                            },
                        ]
                    }
                },
            }
        if run_id == "fixture-bivariate-run":
            return {
                **self._bivariate_run(),
                "artifacts": {
                    "bivariate_rows": {
                        "items": [
                            {
                                "left_isin": "DE000TEST01",
                                "left_exchange": "XETRA",
                                "left_code": "AAA",
                                "right_isin": "DE000TEST02",
                                "right_exchange": "XETRA",
                                "right_code": "BBB",
                                "n_observations": 252,
                                "pearson_correlation": 0.21,
                                "spearman_correlation": 0.18,
                                "covariance": 0.002,
                                "downside_correlation": 0.28,
                                "lower_tail_dependence": 0.07,
                                "drawdown_overlap_rate": 0.19,
                            }
                        ]
                    }
                },
            }
        if run_id == "fixture-multivariate-run":
            return self._multivariate_detail()
        raise KeyError(run_id)

    def _universe_id(self) -> str:
        return f"fixture-universe-{self.universe_revision}"

    def _universe(self) -> dict[str, object]:
        return {
            "universe_id": self._universe_id(),
            "version": self.universe_revision,
            "source_snapshot_id": f"market_source_snapshot_fixture_{self.universe_revision}",
            "member_count": 2,
            "created_at": "2026-08-30T00:00:00+00:00",
            "published_at": "2026-08-30T00:00:00+00:00",
            "members": [
                {"isin": "DE000TEST01", "exchange": "XETRA", "code": "AAA"},
                {"isin": "DE000TEST02", "exchange": "XETRA", "code": "BBB"},
            ],
        }

    @staticmethod
    def _univariate_run() -> dict[str, object]:
        return {
            "run_id": "fixture-univariate-run",
            "stage": "univariate",
            "status": "succeeded",
            "input_ref": "fixture-universe-1",
            "input_snapshot_id": "market_source_snapshot_fixture_1",
            "algorithm_version": "univariate.statistics.v2",
        }

    @staticmethod
    def _selection() -> dict[str, object]:
        return {
            "selection_id": "fixture-selection-1",
            "source_run_id": "fixture-univariate-run",
            "version": 1,
            "member_count": 2,
            "created_at": "2026-08-30T00:00:01+00:00",
            "published_at": "2026-08-30T00:00:01+00:00",
            "members": [
                {"isin": "DE000TEST01", "exchange": "XETRA", "code": "AAA"},
                {"isin": "DE000TEST02", "exchange": "XETRA", "code": "BBB"},
            ],
        }

    @staticmethod
    def _bivariate_run() -> dict[str, object]:
        return {
            "run_id": "fixture-bivariate-run",
            "stage": "bivariate",
            "status": "succeeded",
            "input_ref": "fixture-selection-1",
            "input_snapshot_id": "market_source_snapshot_fixture_1",
            "algorithm_version": "bivariate.statistics.v1",
        }

    @staticmethod
    def _multivariate_run(objective: str) -> dict[str, object]:
        return {
            "run_id": "fixture-multivariate-run",
            "stage": "multivariate",
            "status": "succeeded",
            "input_ref": "fixture-bivariate-run",
            "input_snapshot_id": "market_source_snapshot_fixture_1",
            "algorithm_version": "multivariate_execution.clean.v1",
            "objective": objective,
        }

    def _multivariate_detail(self) -> dict[str, object]:
        return {
            **self._multivariate_run("return_risk"),
            "decision": {
                "objective": "return_risk",
                "winning_candidate_id": "candidate-fixture",
                "requested_method": "minimum_variance",
                "actual_method": "minimum_variance",
                "available": True,
                "production_eligible": True,
                "reason": None,
                "document": {
                    "median_post_cost_return": 0.075,
                    "median_volatility": 0.10,
                    "ranking_basis": "walk_forward_out_of_sample_only",
                },
            },
            "artifacts": {
                "candidates": {
                    "items": [
                        {
                            "candidate_id": "candidate-fixture",
                            "method": "minimum_variance",
                            "max_drawdown": -0.13,
                            "weights": [
                                {
                                    "isin": "DE000TEST01",
                                    "exchange": "XETRA",
                                    "code": "AAA",
                                    "weight": 0.55,
                                },
                                {
                                    "isin": "DE000TEST02",
                                    "exchange": "XETRA",
                                    "code": "BBB",
                                    "weight": 0.45,
                                },
                            ],
                        }
                    ]
                },
                "validation": {
                    "items": [
                        {
                            "kind": "scorecard",
                            "candidate_id": "candidate-fixture",
                            "method": "minimum_variance",
                            "median_post_cost_return": 0.075,
                            "median_volatility": 0.10,
                        },
                        {
                            "kind": "walk_forward",
                            "candidate_id": "candidate-fixture",
                            "status": "complete",
                            "max_drawdown": -0.14,
                        },
                    ]
                },
                "risk_contributions": {
                    "items": [
                        {
                            "candidate_id": "candidate-fixture",
                            "isin": "DE000TEST01",
                            "exchange": "XETRA",
                            "code": "AAA",
                            "percent_risk_contribution": 0.52,
                        },
                        {
                            "candidate_id": "candidate-fixture",
                            "isin": "DE000TEST02",
                            "exchange": "XETRA",
                            "code": "BBB",
                            "percent_risk_contribution": 0.48,
                        },
                    ]
                },
                "performance": {
                    "portfolio_series": [
                        {
                            "candidate_id": "candidate-fixture",
                            "method": "minimum_variance",
                            "values": [
                                {"date": "2026-01-31", "return": 0.01},
                                {"date": "2026-02-28", "return": 0.025},
                            ],
                        }
                    ]
                },
            },
        }


__all__ = ["DashParityFixtureService", "FixturePublicError"]
