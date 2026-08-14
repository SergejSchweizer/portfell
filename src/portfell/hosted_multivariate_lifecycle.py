"""Small lifecycle adapter for persisted Multivariate runs and workflow projections."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from portfell.hosted_api_state import MultivariateRunRecord
from portfell.hosted_multivariate_run_repository import MultivariateRunRepository


class MultivariateRunLifecycle:
    """Persist run transitions and refresh the owning project's compact workflow."""

    def __init__(
        self,
        runs: MultivariateRunRepository,
        workflow_projector: Callable[[str, str], object] | None,
        persist: Callable[[], None],
    ) -> None:
        self._runs = runs
        self._workflow_projector = workflow_projector
        self._persist = persist

    def save(self, run: MultivariateRunRecord, *, make_current: bool = False) -> None:
        self._runs.save(run, make_current=make_current)
        if self._workflow_projector is not None:
            self._workflow_projector(run.user_id, run.project_id)

    def advance(self, user_id: str, run_id: str, phase: str, completed_units: int) -> None:
        current = self._runs.get(user_id=user_id, run_id=run_id)
        if current is None or current.status != "running":
            return
        completed = max(current.completed_units, min(completed_units, current.total_units))
        self.save(
            replace(
                current,
                phase=phase if completed > current.completed_units else current.phase,
                completed_units=completed,
            )
        )
        self._persist()
