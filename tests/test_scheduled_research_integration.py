from pathlib import Path

from portfell.multivariate.contracts.common import ListingIdentity
from portfell.multivariate.contracts.objectives import OptimizationObjective
from portfell.scheduled_research.integration import run_sunday_cycle
from portfell.scheduled_research.market_refresh import ActiveProjectUniverse, MarketRefreshCallable
from portfell.scheduled_research.project_cycle import ScheduledResearchService, StageOutcome


class Runtime:
    def __init__(self) -> None:
        self.refresh_calls = 0
        self.stage_calls: list[tuple[str, str]] = []

    def active_projects(self) -> tuple[ActiveProjectUniverse, ...]:
        shared = ListingIdentity("DE000A", "XETRA", "AAA")
        second = ListingIdentity("DE000B", "XETRA", "BBB")
        return (
            ActiveProjectUniverse("beta", (shared, second)),
            ActiveProjectUniverse("alpha", (shared,)),
        )

    def market_refresh(self) -> MarketRefreshCallable:
        def refresh(listings: tuple[ListingIdentity, ...]) -> tuple[str, int]:
            self.refresh_calls += 1
            assert len(listings) == 2
            return "market-r1", 6

        return refresh

    def research_service(self) -> ScheduledResearchService:
        runtime = self

        class Service:
            def persisted_objective(self, *, project_slug: str) -> str | None:
                return None if project_slug == "alpha" else OptimizationObjective.MINIMUM_RISK.value

            def ensure_univariate(self, *, project_slug: str, market_revision: str) -> StageOutcome:
                runtime.stage_calls.append((project_slug, "univariate"))
                assert market_revision == "market-r1"
                return StageOutcome("univariate", f"u-{project_slug}", "complete", reused=True)

            def ensure_bivariate(self, *, project_slug: str, univariate_run_id: str) -> StageOutcome:
                runtime.stage_calls.append((project_slug, "bivariate"))
                assert univariate_run_id == f"u-{project_slug}"
                return StageOutcome("bivariate", f"b-{project_slug}", "complete")

            def ensure_multivariate(
                self,
                *,
                project_slug: str,
                bivariate_run_id: str,
                objective: OptimizationObjective,
            ) -> StageOutcome:
                runtime.stage_calls.append((project_slug, "multivariate"))
                assert bivariate_run_id == f"b-{project_slug}"
                expected = (
                    OptimizationObjective.RETURN_RISK
                    if project_slug == "alpha"
                    else OptimizationObjective.MINIMUM_RISK
                )
                assert objective is expected
                return StageOutcome("multivariate", f"m-{project_slug}", "complete")

        return Service()


def test_sunday_cycle_refreshes_once_then_runs_each_project_in_dependency_order(tmp_path: Path) -> None:
    runtime = Runtime()
    result = run_sunday_cycle(
        cycle_date="2026-08-23",
        runtime=runtime,
        lock_path=tmp_path / "sunday.lock",
    )

    assert result.lock_acquired is True
    assert runtime.refresh_calls == 1
    assert runtime.stage_calls == [
        ("alpha", "univariate"),
        ("alpha", "bivariate"),
        ("alpha", "multivariate"),
        ("beta", "univariate"),
        ("beta", "bivariate"),
        ("beta", "multivariate"),
    ]
    assert result.summary.project_count == 2
    assert result.summary.successful_projects == 2
    assert result.summary.failed_projects == 0
    assert result.summary.reused_runs == 2
    assert result.summary.new_runs == 4
