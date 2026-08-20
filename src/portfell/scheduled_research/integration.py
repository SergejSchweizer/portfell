"""Final Sunday full-research integration over the three independent stage PRs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from portfell.scheduled_research.cycle_summary import CycleSummary
from portfell.scheduled_research.market_refresh import (
    ActiveProjectUniverse,
    MarketRefreshCallable,
    refresh_active_union_once,
)
from portfell.scheduled_research.project_cycle import ScheduledResearchService, run_project_cycle
from portfell.scheduled_research.scheduler import ProjectTerminal, coordinate_cycle, cycle_lock


class SundayRuntime(Protocol):
    """Production adapter boundary; implementations reuse existing market/manual run authorities."""

    def active_projects(self) -> tuple[ActiveProjectUniverse, ...]: ...

    def market_refresh(self) -> MarketRefreshCallable: ...

    def research_service(self) -> ScheduledResearchService: ...


@dataclass(frozen=True, slots=True)
class SundayCycleResult:
    summary: CycleSummary
    lock_acquired: bool


def run_sunday_cycle(
    *,
    cycle_date: str,
    runtime: SundayRuntime,
    lock_path: Path,
) -> SundayCycleResult:
    """Refresh the active union once, then run isolated project research in stable order."""

    with cycle_lock(lock_path) as acquired:
        if not acquired:
            return SundayCycleResult(
                CycleSummary(cycle_date, None, 0, 0, 0, 0, 0),
                False,
            )
        projects = runtime.active_projects()
        project_by_slug = {project.project_slug: project for project in projects}
        service = runtime.research_service()
        market_summary: dict[str, object] = {}

        def refresh_market() -> str:
            result = refresh_active_union_once(
                projects=projects,
                cycle_date=cycle_date,
                refresh=runtime.market_refresh(),
            )
            market_summary["revision"] = result.revision
            return result.revision

        def run_project(project_slug: str, revision: str) -> ProjectTerminal:
            if project_slug not in project_by_slug:
                raise KeyError(project_slug)
            result = run_project_cycle(
                project_slug=project_slug,
                market_revision=revision,
                service=service,
            )
            outcomes = (result.univariate, result.bivariate, result.multivariate)
            return ProjectTerminal(
                project_slug=project_slug,
                successful=result.multivariate.successful,
                reused_runs=sum(outcome.reused for outcome in outcomes if outcome.successful),
                new_runs=sum((not outcome.reused) for outcome in outcomes if outcome.successful),
            )

        summary = coordinate_cycle(
            cycle_date=cycle_date,
            project_slugs=tuple(project_by_slug),
            refresh_market=refresh_market,
            run_project=run_project,
        )
        return SundayCycleResult(summary, True)
