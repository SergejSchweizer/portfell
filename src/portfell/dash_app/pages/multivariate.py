"""Multivariate Dash page rendering only persisted optimizer/OOS artifacts."""

# Plotly/Dash payloads are dynamically typed at this UI adapter boundary.
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportArgumentType=false, reportAttributeAccessIssue=false

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, cast

import plotly.graph_objects as go  # pyright: ignore[reportMissingTypeStubs]
from dash import html
from dash.development.base_component import Component

from portfell.dash_app.candidate_structure_presenters import candidate_structure_view
from portfell.dash_app.components import (
    ChartCard,
    ControlBar,
    EmptyState,
    ErrorState,
    KpiCard,
    PageHeader,
    StatusBanner,
    TableCard,
    UnavailableData,
)
from portfell.dash_app.contracts import MULTIVARIATE_OBJECTIVES
from portfell.dash_app.figures import apply_portfell_template
from portfell.dash_app.structure_presenters import universe_structure_view


class MultivariateService(Protocol):
    def workflow_state(self) -> dict[str, object]: ...

    def multivariate_summary(self, run_id: str) -> dict[str, object]: ...

    def multivariate_artifact(self, run_id: str, artifact_type: str) -> dict[str, object]: ...

    def run_multivariate(
        self,
        *,
        selection_id: str,
        bivariate_run_id: str,
        objective: str = "return_risk",
    ) -> dict[str, object]: ...

    def run_detail(self, run_id: str) -> dict[str, object]: ...

    def univariate_chart_sample(self, run_id: str, *, limit: int = 5000) -> dict[str, object]: ...


def multivariate_page_data(service: MultivariateService) -> dict[str, object]:
    workflow = service.workflow_state()
    active_job = _mapping(workflow.get("active_job"))
    selection = _mapping(workflow.get("univariate_selection"))
    stages = _mapping(workflow.get("stages")) or {}
    bivariate = _mapping(stages.get("bivariate"))
    stage = _mapping(stages.get("multivariate"))
    univariate_stage = _mapping(stages.get("univariate"))
    detail = stage
    if stage and stage.get("run_id") and stage.get("status") == "succeeded":
        run_id = str(stage["run_id"])
        if hasattr(service, "multivariate_summary"):
            summary = service.multivariate_summary(run_id)
            detail = _mapping(summary.get("run")) or stage
            detail = {
                **detail,
                "decision": summary.get("decision"),
                "artifacts": {
                    artifact_type: service.multivariate_artifact(run_id, artifact_type)
                    for artifact_type in (
                        "candidates",
                        "validation",
                        "risk_contributions",
                        "performance",
                        "multivariate.structure@v2",
                        "multivariate.structure@v3",
                        "multivariate.candidate_structure@v2",
                    )
                    if artifact_type in cast(list[object], summary.get("artifact_types", []))
                },
            }
        else:
            detail = service.run_detail(run_id)
    artifacts = (_mapping(detail.get("artifacts")) or {}) if detail else {}
    decision = _mapping(detail.get("decision")) if detail else None
    decision_doc = _mapping(decision.get("document")) if decision else None
    winner_id = None if decision is None else decision.get("winning_candidate_id")
    candidates = _items(artifacts.get("candidates") if artifacts else None)
    validation = _items(artifacts.get("validation") if artifacts else None)
    contributions = _items(artifacts.get("risk_contributions") if artifacts else None)
    performance = _mapping(artifacts.get("performance")) if artifacts else None
    structure_document = _mapping(
        artifacts.get("multivariate.structure@v3")
        or artifacts.get("multivariate.structure@v2")
    )
    candidate_structure_document = _mapping(artifacts.get("multivariate.candidate_structure@v2"))
    # Multivariate performance is scoped to the exact selection consumed by
    # the successful Bivariate run. Never plot a broader/stale Univariate
    # selection when Bivariate evidence is missing or belongs to another
    # selection.
    bivariate_matches_selection = (
        bivariate is not None
        and selection is not None
        and bivariate.get("status") == "succeeded"
        and bivariate.get("input_ref") == selection.get("selection_id")
    )
    selected_ids = (
        {
            str(row.get("isin"))
            for row in _mappings(selection.get("members") if selection else None)
            if row.get("isin") not in {None, ""}
        }
        if bivariate_matches_selection
        else set()
    )
    cumulative_rows: list[dict[str, object]] = []
    if univariate_stage and univariate_stage.get("status") == "succeeded":
        reader = getattr(service, "univariate_chart_sample", None)
        run_id = univariate_stage.get("run_id")
        if callable(reader) and run_id:
            try:
                result = reader(str(run_id), limit=5000)
                cumulative_rows = [
                    row
                    for row in _mappings(result.get("rows"))
                    if (not selected_ids or str(row.get("isin")) in selected_ids)
                    and isinstance(
                        row.get("cumulative_extended_return", row.get("cumulative_log_return")),
                        int | float,
                    )
                ]
            except Exception:
                cumulative_rows = []
    winner = next((row for row in candidates if row.get("candidate_id") == winner_id), None)
    # A run can legitimately finish with no production winner when OOS
    # evidence is unavailable.  Candidate/performance plots should still be
    # useful in that state; use the first feasible candidate only as a display
    # fallback and never promote it to the persisted decision.
    display_candidate = winner or next(
        (row for row in candidates if row.get("status") == "feasible"), None
    )
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
        "active_job": active_job,
        "selected_cumulative_log_returns": cumulative_rows,
        "run": detail,
        "artifacts": artifacts,
        "decision": decision,
        "decision_document": decision_doc,
        "winner": winner,
        "display_candidate": display_candidate,
        "winner_id": winner_id,
        "candidates": candidates,
        "validation": validation,
        "risk_contributions": contributions,
        "performance": performance,
        "universe_structure": (
            universe_structure_view(structure_document) if structure_document else None
        ),
        "candidate_structure": (
            candidate_structure_view(
                candidate_structure_document,
                persisted_winning_candidate_id=(
                    str(winner_id) if isinstance(winner_id, str) else None
                ),
            )
            if candidate_structure_document
            else None
        ),
        "winner_oos_return": (
            None if decision_doc is None else decision_doc.get("median_post_cost_return")
        ),
        "winner_oos_risk": None if decision_doc is None else decision_doc.get("median_volatility"),
        "winner_max_drawdown": min(drawdowns) if drawdowns else None,
        "production_eligibility": None if decision is None else decision.get("production_eligible"),
        "ready": (
            detail is not None and detail.get("status") == "succeeded" and decision is not None
        ),
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
    display_candidate = _mapping(model.get("display_candidate")) or winner
    candidates = _mappings(model.get("candidates"))
    validation = _mappings(model.get("validation"))
    contributions = _mappings(model.get("risk_contributions"))
    performance = _mapping(model.get("performance"))
    active_job = _mapping(model.get("active_job")) or {}
    cumulative_rows = _mappings(model.get("selected_cumulative_log_returns"))
    selected_isins = {
        str(row.get("isin"))
        for row in _mappings(selection.get("members") if selection else None)
        if row.get("isin") not in {None, ""}
    }
    universe_structure = _mapping(model.get("universe_structure"))
    candidate_structure = _mapping(model.get("candidate_structure"))
    bivariate_matches_selection = (
        bivariate is not None
        and selection is not None
        and bivariate.get("status") == "succeeded"
        and bivariate.get("input_ref") == selection.get("selection_id")
    )
    children: list[Component] = [
        PageHeader(
            "Multivariate",
            "Optimize candidate portfolios and select the final portfolio from "
            "out-of-sample evidence.",
        ),
        ControlBar(
            [
                html.Button(
                    children="Optimize portfolio",
                    id="multivariate-optimize",
                    className="pf-button pf-button-primary",
                    disabled=(
                        selection is None
                        or bivariate is None
                        or not bivariate_matches_selection
                        or (run or {}).get("status") in {"queued", "running"}
                        or (active_job.get("status") in {"queued", "running"})
                    ),
                ),
            ],
            component_id="multivariate-controls",
        ),
    ]
    if bivariate is not None and not bivariate_matches_selection:
        children.append(
            StatusBanner(
                "Bivariate results are for a different selection. Compute Bivariate "
                "statistics for the current Univariate selection before optimizing."
            )
        )
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
                "Cumulative Extended Return — Bivariate Selected ISINs",
                _cumulative_extended_return_figure(performance, cumulative_rows, selected_isins),
                graph_id="multivariate-selected-cumulative-log-return",
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
                _allocation_figure(display_candidate),
                graph_id="multivariate-allocation",
            ),
            ChartCard(
                "Risk Contribution",
                _risk_contribution_figure(
                    contributions,
                    model.get("winner_id")
                    if model.get("winner_id") is not None
                    else (display_candidate or {}).get("candidate_id"),
                ),
                graph_id="multivariate-risk-contribution",
            ),
            *(_structure_cards(universe_structure, candidate_structure)),
            TableCard(
                "Final Portfolio",
                (
                    [_final_portfolio(winner)]
                    if winner
                    else [UnavailableData("Final weights are unavailable.")]
                ),
                component_id="multivariate-final-portfolio",
            ),
            _decision_card(decision, run),
        ]
    )
    return html.Div(children, className="pf-page", id="multivariate-page")


def _structure_cards(
    universe: Mapping[str, object] | None, candidate: Mapping[str, object] | None
) -> tuple[Component, ...]:
    """Render persisted structural evidence only; unavailable evidence remains explicit."""
    if universe is None or candidate is None:
        return (UnavailableData("Structural evidence is unavailable for this run."),)
    diversification = _mapping(universe.get("structural_diversification")) or {}
    clusters = _mappings(universe.get("risk_clusters"))
    stability = _mapping(universe.get("structural_stability")) or {}
    candidate_rows = _mappings(candidate.get("candidate_structural_risk"))
    return (
        ChartCard("PCA Spectrum", _pca_spectrum_figure(universe.get("pca_spectrum")), graph_id="multivariate-pca-spectrum"),
        TableCard("Structural Diversification", [html.Pre(str(diversification))]),
        TableCard("Risk Clusters", [html.Pre(str(clusters))]),
        TableCard("Structural Stability", [html.Pre(str(stability))]),
        TableCard("Candidate Structural Risk", [html.Pre(str(candidate_rows))]),
        ChartCard("PCA Risk Contribution", _pca_risk_contribution_figure(candidate.get("pca_risk_contribution")), graph_id="multivariate-pca-risk-contribution"),
        ChartCard(
            "Cluster Risk Contribution",
            _cluster_risk_contribution_figure(candidate.get("cluster_risk_contribution")),
            graph_id="multivariate-cluster-risk-contribution",
        ),
    )


def _pca_spectrum_figure(value: object) -> go.Figure | None:
    document = _mapping(value)
    traces: list[go.Bar] = []
    for label, key, colour in (("Covariance", "covariance", "#2563eb"), ("Correlation", "correlation", "#14b8a6")):
        row = _mapping(document.get(key))
        values = [_number(item) for item in cast(list[object], row.get("explained_variance", [])) if _number(item) is not None]
        if values:
            traces.append(go.Bar(x=[f"PC {index + 1}" for index in range(len(values))], y=values, name=label, marker_color=colour, customdata=[[label, index + 1] for index in range(len(values))], hovertemplate="%{customdata[0]} PC %{customdata[1]}<br>Explained variance=%{y:.2%}<extra></extra>"))
    if not traces:
        return None
    figure = go.Figure(traces)
    figure.update_layout(barmode="group")
    return apply_portfell_template(figure, x_title="Principal component", y_title="Explained variance")


def _pca_risk_contribution_figure(value: object) -> go.Figure | None:
    rows = [row for row in _mappings(value) if _number(row.get("percent_portfolio_variance")) is not None]
    if not rows:
        return None
    figure = go.Figure(go.Bar(x=[str(row.get("component_id", "")) for row in rows], y=[_number(row.get("percent_portfolio_variance")) for row in rows], marker_color="#7c3aed", customdata=[[row.get("component_id")] for row in rows], hovertemplate="%{customdata[0]}<br>Portfolio variance=%{y:.2%}<extra></extra>"))
    return apply_portfell_template(figure, x_title="Principal component", y_title="Portfolio variance contribution")


def _cluster_risk_contribution_figure(value: object) -> go.Figure | None:
    rows = [row for row in _mappings(value) if _number(row.get("gross_abs_risk_share", row.get("signed_percent_variance"))) is not None]
    if not rows:
        return None
    values = [_number(row.get("gross_abs_risk_share", row.get("signed_percent_variance"))) for row in rows]
    figure = go.Figure(go.Bar(x=[str(row.get("cluster_id", "")) for row in rows], y=values, marker_color="#f59e0b", customdata=[[row.get("cluster_id")] for row in rows], hovertemplate="%{customdata[0]}<br>Gross risk share=%{y:.2%}<extra></extra>"))
    return apply_portfell_template(figure, x_title="Risk cluster", y_title="Gross risk share")


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
    return apply_portfell_template(
        figure,
        x_title="Median OOS volatility",
        y_title="Median post-cost OOS return",
    )


def _performance_figure(
    performance: Mapping[str, object] | None, winner_id: object
) -> go.Figure | None:
    if performance is None:
        return None
    series = _mappings(performance.get("portfolio_series"))
    winner = next(
        (row for row in series if row.get("candidate_id") == winner_id),
        None,
    )
    if winner is None:
        winner = next((row for row in series if row.get("status", "feasible") == "feasible"), None)
    if winner is None:
        return None
    values = _mappings(winner.get("values"))
    values = tuple(
        row for row in values
        if row.get("date") is not None
        and _number(row.get("cumulative_extended_return", row.get("return"))) is not None
    )
    if not values:
        return None
    figure = go.Figure(
        go.Scatter(
            x=[row.get("date") for row in values],
            y=[
                _number(row.get("cumulative_extended_return", row.get("return")))
                for row in values
            ],
            mode="lines",
            name="Winning portfolio",
            hovertemplate="Date=%{x}<br>Cumulative return=%{y:.2%}<extra></extra>",
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
            hovertemplate=(
                "Candidate %{customdata[0]}<br>Persisted max drawdown %{y}<extra></extra>"
            ),
            name="Persisted max drawdown",
        )
    )
    return apply_portfell_template(figure, x_title="Candidate", y_title="Max drawdown")


def _allocation_figure(winner: Mapping[str, object] | None) -> go.Figure | None:
    if winner is None:
        return None
    weights = tuple(
        row for row in _mappings(winner.get("weights"))
        if _number(row.get("weight")) is not None
    )
    if not weights:
        return None
    figure = go.Figure(
        go.Bar(
            x=[f"{row.get('isin')} / {row.get('exchange')} / {row.get('code')}" for row in weights],
            y=[_number(row.get("weight")) for row in weights],
            customdata=[[row.get("isin"), row.get("exchange"), row.get("code")] for row in weights],
            hovertemplate="ISIN=%{customdata[0]}<br>Exchange=%{customdata[1]}<br>Code=%{customdata[2]}<br>Weight=%{y:.2%}<extra></extra>",
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
    # Older persisted artifacts omitted candidate_id for the sole displayed
    # candidate. Keep those valid rows visible instead of showing an empty
    # chart after a successful run.
    if not selected and winner_id is not None:
        selected = [
            row for row in rows
            if row.get("candidate_id") in {None, ""}
            and isinstance(row.get("percent_risk_contribution"), int | float)
        ]
    if not selected:
        return None
    figure = go.Figure(
        go.Bar(
            x=[
                f"{row.get('isin')} / {row.get('exchange')} / {row.get('code')}" for row in selected
            ],
            y=[_number(row.get("percent_risk_contribution")) for row in selected],
            customdata=[[row.get("isin"), row.get("exchange"), row.get("code")] for row in selected],
            hovertemplate="ISIN=%{customdata[0]}<br>Exchange=%{customdata[1]}<br>Code=%{customdata[2]}<br>Risk contribution=%{y:.2%}<extra></extra>",
            name="Risk contribution",
        )
    )
    return apply_portfell_template(figure, x_title="Listing", y_title="Percent risk contribution")


def _final_portfolio(winner: Mapping[str, object]) -> Component:
    weights = _mappings(winner.get("weights"))
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
            [
                item
                for label, value in values
                for item in (html.Dt(label), html.Dd(_display(value)))
            ],
            className="pf-evidence-list",
        )
    return html.Section(
        [html.H2("Decision", className="pf-card-title"), html.Div(body, className="pf-card-body")],
        className="pf-card pf-decision-card",
        id="multivariate-decision",
    )


def _cumulative_extended_return_figure(
    performance: Mapping[str, object] | None,
    fallback_rows: Sequence[Mapping[str, object]],
    selected_isins: set[str] | None = None,
) -> go.Figure:
    figure = go.Figure()
    series = _mappings(performance.get("instrument_series")) if performance else ()
    aligned_dates: list[str] = []
    if selected_isins:
        series = tuple(row for row in series if str(row.get("isin")) in selected_isins)
    if not series and fallback_rows:
        grouped: dict[str, list[dict[str, object]]] = {}
        for row in fallback_rows:
            isin = str(row.get("isin", ""))
            if isin and row.get("date") is not None and _number(
                row.get("cumulative_extended_return", row.get("cumulative_log_return", row.get("return")))
            ) is not None:
                grouped.setdefault(isin, []).append(row)
        series = tuple(
            {"isin": isin, "values": sorted(rows, key=lambda item: str(item.get("date", "")))}
            for isin, rows in sorted(grouped.items())
        )
    if series:
        # Bivariate statistics are computed on one aligned calendar.  Display
        # exactly that common interval instead of allowing an instrument with a
        # longer history to extend the x-axis beyond the bivariate universe.
        date_sets = [
            {str(value.get("date")) for value in _mappings(row.get("values")) if value.get("date")}
            for row in series
        ]
        aligned_input = bool(date_sets) and all(date_sets)
        common_dates = set.intersection(*date_sets) if aligned_input else set()
        # A common calendar is preferred, but a sparse/short dataset must not
        # make every trace disappear. In that case retain each instrument's
        # available dates and let Plotly render gaps independently.
        use_common = bool(common_dates)
        aligned_dates = sorted(common_dates) if use_common else []
        for row in sorted(series, key=lambda item: str(item.get("isin", ""))):
            values = tuple(
                value
                for value in _mappings(row.get("values"))
                if value.get("date") is not None
                and _number(value.get("cumulative_extended_return", value.get("return"))) is not None
                and (not use_common or str(value.get("date")) in common_dates)
            )
            if not values:
                continue
            figure.add_trace(
                go.Scatter(
                    x=[str(value.get("date", "")) for value in values],
                    y=[
                        _number(value.get("cumulative_extended_return", value.get("return")))
                        for value in values
                    ],
                    mode="lines",
                    name=str(row.get("isin", "")),
                    line={"color": "#c7cdd4", "width": 1.2},
                    customdata=[[str(row.get("isin", ""))]] * len(values),
                    hovertemplate=(
                        "ISIN=%{customdata[0]}<br>Date=%{x}<br>"
                        "Cumulative extended return=%{y:.2%}<extra></extra>"
                    ),
                )
            )
    else:
        figure.add_annotation(
            text="Chart data is not available yet.", x=0.5, y=0.5, showarrow=False
        )
    figure.update_layout(
        xaxis_title="Time",
        yaxis_title="Cumulative extended return",
        yaxis={"tickformat": ".1%"},
        height=360,
        margin={"l": 60, "r": 20, "t": 20, "b": 80},
        showlegend=False,
    )
    if aligned_dates:
        figure.update_xaxes(range=[aligned_dates[0], aligned_dates[-1]])
    return apply_portfell_template(figure)


def _items(value: object) -> tuple[dict[str, object], ...]:
    mapping = _mapping(value) or {}
    return _mappings(mapping.get("items"))


def _mapping(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _mappings(value: object) -> tuple[dict[str, object], ...]:
    raw = cast(list[object] | tuple[object, ...], value) if isinstance(value, list | tuple) else ()
    rows: list[dict[str, object]] = []
    for item in raw:
        row = _mapping(item)
        if row is not None:
            rows.append(row)
    return tuple(rows)


def _empty_model() -> dict[str, object]:
    return {
        "selection": None,
        "bivariate": None,
        "active_job": None,
        "selected_cumulative_log_returns": (),
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


def _number(value: object) -> float | None:
    """Normalize finite numeric plot values and reject booleans/invalid data."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    result = float(value)
    return result if result == result and abs(result) != float("inf") else None


def _error_code(error: Exception) -> str:
    code = getattr(error, "code", None)
    return str(code) if isinstance(code, str) else "unavailable"


__all__ = ["build_page", "multivariate_page_data", "optimize_portfolio"]
