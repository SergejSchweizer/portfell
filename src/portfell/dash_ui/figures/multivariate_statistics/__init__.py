"""Multivariate optimizer professional figure factories."""

from portfell.dash_ui.figures.multivariate_statistics.audit import decision_audit_figure
from portfell.dash_ui.figures.multivariate_statistics.candidates import candidate_return_risk_figure
from portfell.dash_ui.figures.multivariate_statistics.history import walk_forward_history_figure

__all__ = ["candidate_return_risk_figure", "decision_audit_figure", "walk_forward_history_figure"]
