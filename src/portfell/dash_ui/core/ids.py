"""Frozen component namespaces used by independently implemented Dash pages."""

from __future__ import annotations

SHELL_NAMESPACE = "shell"
METADATA_NAMESPACE = "metadata"
UNIVARIATE_NAMESPACE = "univariate"
BIVARIATE_NAMESPACE = "bivariate"
MULTIVARIATE_NAMESPACE = "multivariate"
RUN_CONTROL_NAMESPACE = "run-control"
UNIVERSE_HISTORY_NAMESPACE = "universe-history"
DECISION_AUDIT_NAMESPACE = "decision-audit"
OBJECTIVE_SELECTOR_ID = "multivariate-objective-selector"
PORTFOLIO_CANDIDATE_FIGURE_ID = "multivariate-portfolio-candidate-oos-return-risk"

NAMESPACES: tuple[str, ...] = (
    SHELL_NAMESPACE,
    METADATA_NAMESPACE,
    UNIVARIATE_NAMESPACE,
    BIVARIATE_NAMESPACE,
    MULTIVARIATE_NAMESPACE,
    RUN_CONTROL_NAMESPACE,
    UNIVERSE_HISTORY_NAMESPACE,
    DECISION_AUDIT_NAMESPACE,
)


def component_id(namespace: str, name: str) -> str:
    """Build a stable component ID and reject unknown namespaces."""

    if namespace not in NAMESPACES:
        raise ValueError(f"unknown component namespace: {namespace}")
    if not name or any(character.isspace() for character in name):
        raise ValueError("component name must be a non-empty whitespace-free token")
    return f"{namespace}-{name}"
