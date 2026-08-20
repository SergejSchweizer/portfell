"""Decision Audit presentation from immutable DecisionArtifact projections."""

from __future__ import annotations

from collections.abc import Iterable

from portfell.multivariate.contracts.common import DECISION_STAGE_ORDER
from portfell.dash_ui.figures.multivariate_statistics.models import DecisionStageView


def decision_audit_figure(stages: Iterable[DecisionStageView]) -> dict[str, object]:
    """Show every frozen decision stage; reasons are displayed, never reconstructed."""

    by_stage = {stage.stage: stage for stage in stages}
    rows: list[DecisionStageView] = []
    for stage_id in DECISION_STAGE_ORDER:
        rows.append(
            by_stage.get(
                stage_id.value,
                DecisionStageView(stage_id.value, "unavailable", "section_not_persisted", (), 0, {}),
            )
        )
    return {
        "data": [
            {
                "type": "bar",
                "orientation": "h",
                "name": "Selected items",
                "y": [row.stage for row in rows],
                "x": [len(row.selected_ids) for row in rows],
                "customdata": [[row.status, row.reason, row.rejected_count] for row in rows],
                "hovertemplate": "%{y}<br>status=%{customdata[0]}<br>reason=%{customdata[1]}<br>selected=%{x}<br>rejected=%{customdata[2]}<extra></extra>",
            }
        ],
        "layout": {
            "title": "Multivariate Decision Audit",
            "xaxis": {"title": "Selected item count"},
            "yaxis": {"title": "Decision stage", "categoryorder": "array", "categoryarray": [stage.value for stage in DECISION_STAGE_ORDER]},
            "uirevision": "multivariate-decision-audit-v1",
        },
    }
