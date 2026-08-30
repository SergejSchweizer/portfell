"""Multivariate Dash page rendering only persisted optimizer/OOS artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, cast

import plotly.graph_objects as go
from dash import dcc, html
from dash.development.base_component import Component

from portfell.dash_app.components import (
    ChartCard,
    ControlBar,
    EmptyState,
    ErrorState,
    HistoryCard,
    KpiCard,
    PageHeader,
    StageFooter,
    StatusBanner,
    TableCard,
    UnavailableData,
)
from portfell.dash_app.contracts import MULTIVARIATE_OBJECTIVES
from portfell.dash_app.figures import apply_portfell_template


class MultivariateService(Protocol):
    def workflow_state(self) -> dict[str, object]: ...

    def run_multivariate(
        self,
        *,
        selection_id: str,
        bivariate_run_id: str,
        objective: str = "return_risk",
    ) -> dict[str, object]: ...

    def run_detail(self, run_id: str) -> dict[str, object]: ...


def multivariate_page_data(service: MultivariateService) -> dict[str, object]:
    workflow = service.workflow_state()
    selection = _mapping(workflow.get("univariate_selection"))
    stages = _mapping(workflow.get("stages"))
    bivariate = _mapping(stages.get("bivariate"))
    stage = _mapping(stages.get("multivariate"))
    detail = service.run_detail(str(stage["run_id"])) if stage and stage.get("run_id") else stage
    artifacts = _mapping(detail.get("artifacts")) if detail else {}
    decision = _mapping(detail.get("decision")) if detail else None
    decision_doc = _mapping(decision.get("document")) if decision else None
    winner_id = None if decision is None else decision.get("winning_candidate_id")
    candidates = _items(artifacts.get("candidates") if artifacts else None)
    validation = _items(artifacts.get("validation") if artifacts else None)
    contributions = _items(artifacts.get("risk_contributions") if artifacts else None)
    performance = _mapping(artifacts.get("performance")) if artifacts else None
    winner = next((row for row in candidates if row.get("candidate_id") == winner_id), None)
    winner_splits = [
        row
        for row in validation
        if row.get("kind") == "walk_forward"
        and row.get("candidate_id") == winner_id
        and row.get("status") == "complete"
    ]
    drawdowns = [
        value
        for row in winner_splits
        if isinstance((value := row.get("max_drawdown")), int | float)
    ]
    return {
        "selection": selection,
        "bivariate": bivariate,
        "run": detail,
        "artifacts": artifacts,
        "decision": decision,
        "decision_document": decision_doc,
        "winner": winner,
        "winner_id": winner_id,
        "candidates": candidates,
        "validation": validation,
        "risk_contributions": contributions,
        "performance": performance,
        "winner_oos_return": None if decision_doc is None else decision_doc.get("median_post_cost_return"),
        "winner_oos_risk": None if decision_doc is None else decision_doc.get("median_volatility"),
        "winner_max_drawdown": min(drawdowns) if drawdowns else None,
        "production_eligibility": None if decision is None else decision.get("production_eligible"),
        "ready": detail is not None and detail.get("status") == "succeeded" and decision is not None,
    }


def optimize_portfolio(
    service: MultivariateService,
    *,
    selection_id: str,
    bivariate_run_id: str,
    objective: str,
) -> dict[str, object]:
    if objective not in MULTIVARIATE_OBJECTIVES:
        raise ValueError("invalid_multivariate_objective")
    return service.run_multivariate(
        selection_id=selection_id,
        bivariate_run_id=bivariate_run_id,
        objective=objective,
    )


def build_page(services: object | None = None) -> Component:
    if services is None:
        return _layout(_empty_model(), message="Application service is unavailable.")
    try:
        model = multivariate_page_data(cast(MultivariateService, services))
    except Exception as error:
        return _layout(_empty_model(), error=_error_code(error))
    return _layout(model)


def _layout(
    model: Mapping[str, object], *, message: str | None = None, error: str | None = None
) -> Component:
    selection = _mapping(model.get("selection"))
    bivariate = _mapping(model.get("bivariate"))
    run = _mapping(model.get("run"))
    decision = _mapping(model.get("decision"))
    winner = _mapping(model.get("winner"))
    candidates = tuple(row for row in model.get("candidates", ()) if isinstance(row, dict))
    validation = tuple(row for row in model.get("validation", ()) if isinstance(row, dict))
    contributions = tuple(
        row for row in model.get("risk_contributions", ()) if isinstance(row, dict)
    )
    performance = _mapping(model.get("performance"))
    children: list[Component] = [
        PageHeader(
            "Multivariate",
            "Optimize candidate portfolios and select the final portfolio from out-of-sample evidence.",
        ),
        ControlBar(
            [
                html.Label(
                    [
                        html.Span("Objective", className="pf-context-label"),
                        dcc.Dropdown(
                            id="multivariate-objective",
                            options=[
                                {"label": value.replace("_", " ").title(), "value": value}
                                for value in MULTIVARIATE_OBJECTIVES
                            ],
                            value="return_risk",
                            clearable=False,
                        ),
                    ]
                ),
                html.Button(
                    "Optimize portfolio",
                    id="multivariate-optimize",
                    className="pf-button pf-button-primary",
                    disabled=selection is None or bivariate is None,
                ),
            ],
            component_id="multivariate-controls",
        ),
    ]
    if error:
        children.append(ErrorState(f"Multivariate unavailable: {error}"))
    elif message:
        children.append(StatusBanner(message))
    children.extend(
        [
            html.Div(
                [
                    KpiCard("Winner OOS return", _display(model.get("winner_oos_return"))),
                    KpiCard("Winner OOS risk", _display(model.get("winner_oos_risk"))),
                    KpiCard("Winner max drawdown", _display(model.get("winner_max_drawdown"))),
                    KpiCard(
                        "Production eligibility",
                        _eligibility(model.get("production_eligibility")),
                    ),
                ],
                className="pf-kpi-grid",
            ),
            ChartCard(
                "Portfolio Candidate OOS Return / Risk",
                _candidate_oos_figure(validation),
                graph_id="multivariate-oos-candidates",
            ),
            ChartCard(
                "Cumulative Performance",
                _performance_figure(performance, model.get("winner_id")),
                graph_id="multivariate-performance",
            ),
            ChartCard(
                "Drawdown",
                _drawdown_figure(candidates),
                graph_id="multivariate-drawdown",
            ),
            ChartCard(
                "Allocation",
                _allocation_figure(winner),
                graph_id="multivariate-allocation",
            ),
            ChartCard(
                "Risk Contribution",
                _risk_contribution_figure(contributions, model.get("winner_id")),
                graph_id="multivariate-risk-contribution",
            ),
            TableCard(
                "Final Portfolio",
                [_final_portfolio(winner)] if winner else [UnavailableData("Final weights are unavailable.")],
                component_id="multivariate-final-portfolio",
            ),
            _decision_card(decision, run),
            HistoryCard([_history(selection, bivariate, run)]),
            StageFooter(
                [
                    StatusBanner(
                        "Production eligible"
                        if model.get("production_eligibility") is True
                        else "Final decision is not production eligible yet.",
                        tone="success" if model.get("production_eligibility") is True else "info",
                    )
                ]
            ),
        ]
    )
    return html.Div(children, className="pf-page", id="multivariate-page")


def _candidate_oos_figure(validation: Sequence[Mapping[str, object]]) -> go.Figure | None:
    rows = [row for row in validation if row.get("kind") == "scorecard"]
    rows = [
        row
        for row in rows
        if isinstance(row.get("median_post_cost_return"), int | float)
        and isinstance(row.get("median_volatility"), int | float)
    ]
    if not rows:
        return None
    figure = go.Figure(
        go.Scatter(
            x=[row["median_volatility"] for row in rows],
            y=[row["median_post_cost_return"] for row in rows],
            mode="markers+text",
            text=[str(row.get("method", "")) for row in rows],
            textposition="top center",
            customdata=[[row.get("candidate_id"), row.get("method")] for row in rows],
            hovertemplate=(
                "Candidate %{customdata[0]}<br>Method %{customdata[1]}"
                "<br>OOS risk %{x}<br>OOS return %{y}<extra></extra>"
            ),
            name="OOS scorecards",
        )
    )
    return apply_portfell_template(figure, x_title="Median OOS volatility", y_title="Median post-cost OOS return")


def _performance_figure(
    performance: Mapping[str, object] | None, winner_id: object
) -> go.Figure | None:
    if performance is None:
        return None
    series = performance.get("portfolio_series")
    if not isinstance(series, list):
        return None
    winner = next(
        (row for row in series if isinstance(row, dict) and row.get("candidate_id") == winner_id),
        None,
    )
    if not isinstance(winner, dict) or not isinstance(winner.get("values"), list):
        return None
    values = [row for row in winner["values"] if isinstance(row, dict)]
    figure = go.Figure(
        go.Scatter(
            x=[row.get("date") for row in values],
            y=[row.get("return") for row in values],
            mode="lines",
            name="Winning portfolio",
        )
    )
    return apply_portfell_template(figure, x_title="Date", y_title="Cumulative return")


def _drawdown_figure(candidates: Sequence[Mapping[str, object]]) -> go.Figure | None:
    rows = [row for row in candidates if isinstance(row.get("max_drawdown"), int | float)]
    if not rows:
        return None
    figure = go.Figure(
        go.Bar(
            x=[str(row.get("method", row.get("candidate_id", ""))) for row in rows],
            y=[row["max_drawdown"] for row in rows],
            customdata=[[row.get("candidate_id")] for row in rows],
            hovertemplate="Candidate %{customdata[0]}<br>Persisted max drawdown %{y}<extra></extra>",
            name="Persisted max drawdown",
        )
    )
    return apply_portfell_template(figure, x_title="Candidate", y_title="Max drawdown")


def _allocation_figure(winner: Mapping[str, object] | None) -> go.Figure | None:
    if winner is None or not isinstance(winner.get("weights"), list):
        return None
    weights = [row for row in winner["weights"] if isinstance(row, dict)]
    if not weights:
        return None
    figure = go.Figure(
        go.Bar(
            x=[f"{row.get('isin')} / {row.get('exchange')} / {row.get('code')}" for row in weights],
            y=[row.get("weight") for row in weights],
            name="Weight",
        )
    )
    return apply_portfell_template(figure, x_title="Listing", y_title="Weight")


def _risk_contribution_figure(
    rows: Sequence[Mapping[str, object]], winner_id: object
) -> go.Figure | None:
    selected = [
        row
        for row in rows
        if row.get("candidate_id") == winner_id
        and isinstance(row.get("percent_risk_contribution"), int | float)
    ]
    if not selected:
        return None
    figure = go.Figure(
        go.Bar(
            x=[f"{row.get('isin')} / {row.get('exchange')} / {row.get('code')}" for row in selected],
            y=[row.get("percent_risk_contribution") for row in selected],
            name="Risk contribution",
        )
    )
    return apply_portfell_template(figure, x_title="Listing", y_title="Percent risk contribution")


def _final_portfolio(winner: Mapping[str, object]) -> Component:
    raw = winner.get("weights")
    weights = [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []
    if not weights:
        return UnavailableData("Final weights are unavailable.")
    columns = ("isin", "exchange", "code", "weight")
    return html.Table(
        [
            html.Thead(html.Tr([html.Th(name) for name in columns])),
            html.Tbody(
                [html.Tr([html.Td(_display(row.get(name))) for name in columns]) for row in weights]
            ),
        ],
        className="pf-table",
    )


def _decision_card(
    decision: Mapping[str, object] | None, run: Mapping[str, object] | None
) -> Component:
    if decision is None:
        body: Component = UnavailableData("No completed OOS decision is available.")
    else:
        values = (
            ("Objective", decision.get("objective")),
            ("Winning candidate", decision.get("winning_candidate_id")),
            ("Requested method", decision.get("requested_method")),
            ("Actual method", decision.get("actual_method")),
            ("Source snapshot", None if run is None else _short(run.get("input_snapshot_id"))),
            ("Algorithm", None if run is None else run.get("algorithm_version")),
            ("Available", decision.get("available")),
            ("Production eligibility", decision.get("production_eligible")),
            ("Reason", decision.get("reason")),
        )
        body = html.Dl(
            [item for label, value in values for item in (html.Dt(label), html.Dd(_display(value)))],
            className="pf-evidence-list",
        )
    return html.Section(
        [html.H2("Decision", className="pf-card-title"), html.Div(body, className="pf-card-body")],
        className="pf-card pf-decision-card",
        id="multivariate-decision",
    )


def _history(
    selection: Mapping[str, object] | None,
    bivariate: Mapping[str, object] | None,
    run: Mapping[str, object] | None,
) -> Component:
    if selection is None and bivariate is None and run is None:
        return EmptyState("No persisted Multivariate history yet.")
    values = (
        ("Univariate selection", None if selection is None else selection.get("selection_id")),
        ("Bivariate run", None if bivariate is None else bivariate.get("run_id")),
        ("Multivariate run", None if run is None else run.get("run_id")),
        ("Status", None if run is None else run.get("status")),
        ("Source snapshot", None if run is None else _short(run.get("input_snapshot_id"))),
        ("Algorithm", None if run is None else run.get("algorithm_version")),
    )
    return html.Dl(
        [item for label, value in values for item in (html.Dt(label), html.Dd(_display(value)))],
        className="pf-evidence-list",
    )


def _items(value: object) -> tuple[dict[str, object], ...]:
    mapping = _mapping(value)
    raw = mapping.get("items") if mapping else None
    if not isinstance(raw, list):
        return ()
    return tuple(cast(dict[str, object], item) for item in raw if isinstance(item, dict))


def _mapping(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _empty_model() -> dict[str, object]:
    return {
        "selection": None,
        "bivariate": None,
        "run": None,
        "artifacts": {},
        "decision": None,
        "winner": None,
        "winner_id": None,
        "candidates": (),
        "validation": (),
        "risk_contributions": (),
        "performance": None,
        "winner_oos_return": None,
        "winner_oos_risk": None,
        "winner_max_drawdown": None,
        "production_eligibility": None,
        "ready": False,
    }


def _eligibility(value: object) -> str:
    if value is True:
        return "Eligible"
    if value is False:
        return "Not eligible"
    return "—"


def _short(value: object) -> str:
    text = "" if value is None else str(value)
    return text[:12] if text else "—"


def _display(value: object) -> str:
    return "—" if value is None else str(value)


def _error_code(error: Exception) -> str:
    code = getattr(error, "code", None)
    return str(code) if isinstance(code, str) else "unavailable"


__all__ = ["build_page", "multivariate_page_data", "optimize_portfolio"]
