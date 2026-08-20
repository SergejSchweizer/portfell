"""Professional Plotly presentation contracts; no financial formulas live here."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AxisContract:
    label: str
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class ProfessionalPlotContract:
    figure_id: str
    title: str
    x_axis: AxisContract
    y_axis: AxisContract
    responsive: bool = True
    accessible_description: str = ""


UNIVARIATE_RETURN_RISK = ProfessionalPlotContract(
    figure_id="univariate-return-risk-universe",
    title="Univariate Return / Risk Universe",
    x_axis=AxisContract("Annualized volatility", "% p.a."),
    y_axis=AxisContract("Annualized geometric return", "% p.a."),
    accessible_description="Return versus annualized volatility for the Univariate listing universe.",
)

BIVARIATE_RETURN_DIVERSIFICATION = ProfessionalPlotContract(
    figure_id="bivariate-return-diversification-universe",
    title="Bivariate Return / Diversification Universe",
    x_axis=AxisContract("Median dependence", None),
    y_axis=AxisContract("Annualized geometric return", "% p.a."),
    accessible_description="Return versus selected median dependence for the Bivariate universe.",
)

MULTIVARIATE_CANDIDATE_RETURN_RISK = ProfessionalPlotContract(
    figure_id="multivariate-portfolio-candidate-oos-return-risk",
    title="Portfolio Candidate OOS Return / Risk",
    x_axis=AxisContract("OOS annualized volatility", "% p.a."),
    y_axis=AxisContract("OOS annualized return", "% p.a."),
    accessible_description="Out-of-sample return versus risk for portfolio candidates.",
)

PROFESSIONAL_PLOTS: tuple[ProfessionalPlotContract, ...] = (
    UNIVARIATE_RETURN_RISK,
    BIVARIATE_RETURN_DIVERSIFICATION,
    MULTIVARIATE_CANDIDATE_RETURN_RISK,
)
