"""In-process, non-response instrumentation for bounded workflow projection reads."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkflowReadObservation:
    """One route-read measurement, intentionally excluding tenant payload data."""

    route: str
    statement_count: int | None
    response_bytes: int
    shared_file_reads: int
    elapsed_seconds: float


@dataclass
class WorkflowReadMetrics:
    """Structured in-process hook used by route and performance tests."""

    observations: list[WorkflowReadObservation] = field(
        default_factory=lambda: list[WorkflowReadObservation]()
    )

    def record(self, observation: WorkflowReadObservation) -> None:
        self.observations.append(observation)
