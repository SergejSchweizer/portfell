"""Bounded worker-capacity rules that reserve resources for interactive services."""

from __future__ import annotations

from collections.abc import Mapping

DEFAULT_MAX_CONCURRENCY = 4
MAX_CONCURRENCY = 8
RESERVED_INTERACTIVE_CPUS = 2


def resolve_worker_concurrency(
    visible_cpus: int | None, *, configured_concurrency: int | None = None
) -> int:
    """Resolve an operator override or a capacity that leaves room for the API."""

    if configured_concurrency is not None:
        if not 1 <= configured_concurrency <= MAX_CONCURRENCY:
            raise ValueError("worker_concurrency_out_of_range")
        return configured_concurrency
    available_cpus = max(1, visible_cpus or 1)
    return min(DEFAULT_MAX_CONCURRENCY, max(1, available_cpus - RESERVED_INTERACTIVE_CPUS))


def worker_concurrency_from_environment(environment: Mapping[str, str]) -> int | None:
    """Read an optional operator override without accepting an empty setting."""

    value = environment.get("PORTFELL_WORKER_CONCURRENCY", "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as error:
        raise ValueError("worker_concurrency_invalid") from error
