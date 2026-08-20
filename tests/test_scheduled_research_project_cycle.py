from portfell.multivariate.contracts.objectives import OptimizationObjective
from portfell.scheduled_research.project_cycle import StageOutcome, run_project_cycle


class FakeService:
    def __init__(self, objective: str | None = None, fail_stage: str | None = None) -> None:
        self.objective = objective
        self.fail_stage = fail_stage
        self.calls: list[str] = []

    def persisted_objective(self, *, project_slug: str) -> str | None:
        self.calls.append(f"objective:{project_slug}")
        return self.objective

    def ensure_univariate(self, *, project_slug: str, market_revision: str) -> StageOutcome:
        self.calls.append(f"univariate:{project_slug}:{market_revision}")
        if self.fail_stage == "univariate":
            return StageOutcome("univariate", None, "failed", reason="boom")
        return StageOutcome("univariate", "u1", "complete", reused=True)

    def ensure_bivariate(self, *, project_slug: str, univariate_run_id: str) -> StageOutcome:
        self.calls.append(f"bivariate:{project_slug}:{univariate_run_id}")
        if self.fail_stage == "bivariate":
            return StageOutcome("bivariate", None, "failed", reason="boom")
        return StageOutcome("bivariate", "b1", "complete")

    def ensure_multivariate(
        self,
        *,
        project_slug: str,
        bivariate_run_id: str,
        objective: OptimizationObjective,
    ) -> StageOutcome:
        self.calls.append(f"multivariate:{project_slug}:{bivariate_run_id}:{objective.value}")
        return StageOutcome("multivariate", "m1", "complete")


def test_project_cycle_runs_dependency_chain_and_uses_default_objective() -> None:
    service = FakeService()
    result = run_project_cycle(project_slug="alpha", market_revision="r1", service=service)

    assert result.objective is OptimizationObjective.RETURN_RISK
    assert result.multivariate.logical_run_id == "m1"
    assert service.calls == [
        "objective:alpha",
        "univariate:alpha:r1",
        "bivariate:alpha:u1",
        "multivariate:alpha:b1:return_risk",
    ]


def test_project_cycle_uses_persisted_objective() -> None:
    service = FakeService(OptimizationObjective.MINIMUM_RISK.value)
    result = run_project_cycle(project_slug="alpha", market_revision="r1", service=service)
    assert result.objective is OptimizationObjective.MINIMUM_RISK
    assert service.calls[-1].endswith(":minimum_risk")


def test_upstream_failure_blocks_only_downstream_stages() -> None:
    service = FakeService(fail_stage="univariate")
    result = run_project_cycle(project_slug="alpha", market_revision="r1", service=service)

    assert result.univariate.status == "failed"
    assert result.bivariate.status == "blocked"
    assert result.multivariate.status == "blocked"
    assert all(not call.startswith("bivariate:") for call in service.calls)
