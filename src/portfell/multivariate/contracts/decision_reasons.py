"""Frozen reason-code registry for auditable Multivariate decisions."""

from enum import StrEnum


class DecisionReasonCode(StrEnum):
    ELIGIBLE = "eligible"
    DATA_UNAVAILABLE = "data_unavailable"
    INSUFFICIENT_HISTORY = "insufficient_history"
    DISTRIBUTION_NOT_ALLOWED = "distribution_not_allowed"
    PARETO_DOMINATED = "pareto_dominated"
    PARETO_SELECTED = "pareto_selected"
    REDUNDANCY_REPRESENTED = "redundancy_represented"
    REDUNDANCY_NOT_REQUIRED = "redundancy_not_required"
    RISK_MODEL_UNAVAILABLE = "risk_model_unavailable"
    SOLVER_NON_CONVERGENCE = "solver_non_convergence"
    SOLVER_INFEASIBLE = "solver_infeasible"
    WALK_FORWARD_UNAVAILABLE = "walk_forward_unavailable"
    OOS_METRIC_UNAVAILABLE = "oos_metric_unavailable"
    OBJECTIVE_WINNER = "objective_winner"
    NOT_APPLICABLE = "not_applicable"
