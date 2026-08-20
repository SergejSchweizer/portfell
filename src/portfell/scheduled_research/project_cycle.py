"""One-project Univariate -> Bivariate -> Multivariate scheduled research chain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from portfell.multivariate.contracts.objectives import DEFAULT_OBJECTIVE, OptimizationObjective


@dataclass(frozen=True, slots=True)
class StageOutcome:
    stage: str
    logical_run_id: str | None
    status: str
    reused: bool = False
    reason: str | None = None

    @property
    def successful(self) -> bool:
        return self.status == "complete"


@dataclass(frozen=True, slots=True)
class ProjectCycleSummary:
    project_slug: str
    objective: OptimizationObjective
    univariate: StageOutcome
    bivariate: StageOutcome
    multivariate: StageOutcome


class ScheduledResearchService(Protocol):
    """Existing manual-run authority consumed by the scheduler; no scheduler-only analytics."""

    def persisted_objective(self, *, project_slug: str) -> str | None: ...

    def ensure_univariate(self, *, project_slug: str, market_revision: str) -> StageOutcome: ...

    def ensure_bivariate(
        self, *, project_slug: str, univariate_run_id: str
    ) -> StageOutcome: ...

    def ensure_multivariate(
        self,
        *,
        project_slug: str,
        bivariate_run_id: str,
        objective: OptimizationObjective,
    ) -> StageOutcome: ...


def _blocked(stage: str, reason: str) -> StageOutcome:
    return StageOutcome(stage, None, "blocked", False, reason)


def run_project_cycle(
    *,
    project_slug: str,
    market_revision: str,
    service: ScheduledResearchService,
) -> ProjectCycleSummary:
    """Reuse/create logical manual runs in strict dependency order with project-local failure."""

    persisted = service.persisted_objective(project_slug=project_slug)
    objective = DEFAULT_OBJECTIVE if persisted is None else OptimizationObjective(persisted)

    univariate = service.ensure_univariate(project_slug=project_slug, market_revision=market_revision)
    if not univariate.successful or univariate.logical_run_id is None:
        return ProjectCycleSummary(
            project_slug,
            objective,
            univariate,
            _blocked("bivariate", "univariate_not_complete"),
            _blocked("multivariate", "univariate_not_complete"),
        )

    bivariate = service.ensure_bivariate(
        project_slug=project_slug,
        univariate_run_id=univariate.logical_run_id,
    )
    if not bivariate.successful or bivariate.logical_run_id is None:
        return ProjectCycleSummary(
            project_slug,
            objective,
            univariate,
            bivariate,
            _blocked("multivariate", "bivariate_not_complete"),
        )

    multivariate = service.ensure_multivariate(
        project_slug=project_slug,
        bivariate_run_id=bivariate.logical_run_id,
        objective=objective,
    )
    return ProjectCycleSummary(project_slug, objective, univariate, bivariate, multivariate)
