from __future__ import annotations

import pytest

from portfell.hosted_worker_capacity import (
    resolve_worker_concurrency,
    worker_concurrency_from_environment,
)


@pytest.mark.parametrize(
    ("visible_cpus", "expected"),
    [
        (None, 1),
        (1, 1),
        (2, 1),
        (3, 1),
        (4, 2),
        (6, 4),
        (32, 4),
    ],
)
def test_default_worker_capacity_reserves_interactive_cpu_capacity(
    visible_cpus: int | None, expected: int
) -> None:
    assert resolve_worker_concurrency(visible_cpus) == expected


def test_operator_worker_capacity_override_is_honored_within_the_safe_range() -> None:
    assert resolve_worker_concurrency(32, configured_concurrency=8) == 8


@pytest.mark.parametrize("configured_concurrency", [0, 9])
def test_operator_worker_capacity_override_rejects_unsafe_values(
    configured_concurrency: int,
) -> None:
    with pytest.raises(ValueError, match="worker_concurrency_out_of_range"):
        resolve_worker_concurrency(8, configured_concurrency=configured_concurrency)


def test_worker_capacity_environment_override_is_optional_and_typed() -> None:
    assert worker_concurrency_from_environment({}) is None
    assert worker_concurrency_from_environment({"PORTFELL_WORKER_CONCURRENCY": " 3 "}) == 3
    with pytest.raises(ValueError, match="worker_concurrency_invalid"):
        worker_concurrency_from_environment({"PORTFELL_WORKER_CONCURRENCY": "many"})
