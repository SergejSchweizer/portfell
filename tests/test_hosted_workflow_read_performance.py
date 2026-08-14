from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from portfell.hosted_project_workflow_reader import PostgresProjectedWorkflowReader
from portfell.hosted_workflow_read_metrics import WorkflowReadMetrics

_PROJECT_COUNT = 100
_MEMBER_COUNT = 25_000


@dataclass
class _Counter:
    value: int = 0

    def read(self) -> int:
        return self.value


class _Clock:
    def __init__(self, seconds_per_read: float) -> None:
        self._value = 0.0
        self._step = seconds_per_read

    def __call__(self) -> float:
        value = self._value
        self._value += self._step
        return value


class _PrecomputedProjectionFixture:
    """100 compact projections representing a 25,000-member precomputed tenant universe."""

    def __init__(self, counter: _Counter) -> None:
        self._counter = counter
        self.member_count = _MEMBER_COUNT
        self.projects: dict[str, tuple[dict[str, object], str]] = {
            f"project-{index:03d}": (
                {
                    "schema_version": 1,
                    "stages": {"univariate_statistics": {"status": "complete"}},
                    "process_overview": {"univariate_statistics_isins": self.member_count},
                },
                f"etag-{index:03d}",
            )
            for index in range(_PROJECT_COUNT)
        }

    def read_current(self, *, user_id: str) -> tuple[dict[str, object], str]:
        assert user_id == "user-1"
        self._counter.value += 1
        return self.projects["project-000"]

    def read_owned(self, *, user_id: str, project_id: str) -> tuple[dict[str, object], str] | None:
        assert user_id == "user-1"
        self._counter.value += 1
        return self.projects.get(project_id)


def _percentile_95(values: list[float]) -> float:
    return sorted(values)[ceil(len(values) * 0.95) - 1]


def _exercise_reader(seconds_per_read: float) -> WorkflowReadMetrics:
    counter = _Counter()
    metrics = WorkflowReadMetrics()
    reader = PostgresProjectedWorkflowReader(
        _PrecomputedProjectionFixture(counter),  # type: ignore[arg-type]
        metrics=metrics,
        statement_count=counter.read,
        clock=_Clock(seconds_per_read),
    )
    reader("user-1", None)
    for index in range(_PROJECT_COUNT):
        reader("user-1", f"project-{index:03d}")
    return metrics


def test_precomputed_100_project_workflow_reads_meet_idle_budgets() -> None:
    metrics = _exercise_reader(0.002)

    assert len(metrics.observations) == _PROJECT_COUNT + 1
    assert all(item.statement_count == 1 for item in metrics.observations)
    assert all(item.shared_file_reads == 0 for item in metrics.observations)
    assert all(item.response_bytes < 256 * 1024 for item in metrics.observations)
    assert _percentile_95([item.elapsed_seconds for item in metrics.observations]) < 0.250


def test_precomputed_100_project_workflow_reads_meet_loaded_budgets() -> None:
    metrics = _exercise_reader(0.020)

    assert _percentile_95([item.elapsed_seconds for item in metrics.observations]) < 1.0
