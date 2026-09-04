from typing import cast

from portfell.app_services.workspace import AppStatePort, CoalescedProgress


class State:
    def __init__(self) -> None:
        self.writes: list[tuple[int, int | None, str]] = []

    def update_job_progress(
        self, job_id: str, *, current: int, total: int | None, phase: str
    ) -> None:
        self.writes.append((current, total, phase))


def test_progress_is_coalesced_to_percentage_buckets_and_terminal_value() -> None:
    state = State()
    progress = CoalescedProgress(cast(AppStatePort, state), "job", 10_000, "pairs")
    for current in range(10_001):
        progress.write(current)
    assert len(state.writes) <= 101
    assert state.writes[0] == (0, 10_000, "pairs")
    assert state.writes[-1] == (10_000, 10_000, "pairs")


def test_progress_never_writes_a_value_above_total() -> None:
    state = State()
    progress = CoalescedProgress(cast(AppStatePort, state), "job", 4, "members")
    progress.write(99)
    assert state.writes == [(4, 4, "members")]
