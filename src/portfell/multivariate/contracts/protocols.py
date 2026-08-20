"""Protocol boundaries keeping Multivariate sibling PRs independent."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from portfell.multivariate.contracts.common import ListingIdentity


class SelectorPort(Protocol):
    def select(self, *, listings: Sequence[ListingIdentity], evidence: Mapping[str, object]) -> object: ...


class CandidateBuilderPort(Protocol):
    def build(self, *, listings: Sequence[ListingIdentity], training_data: object, settings: object) -> Sequence[object]: ...


class DecisionSinkPort(Protocol):
    def put_decision(self, *, decision_id: str, canonical_payload: str) -> None: ...


class HistorySinkPort(Protocol):
    def put_snapshot(self, *, snapshot_id: str, canonical_payload: str) -> None: ...


class MultivariateReadPort(Protocol):
    def current_run(self, *, project_slug: str) -> Mapping[str, object] | None: ...

    def decision_section(self, *, project_slug: str, run_id: str, section_id: str) -> Mapping[str, object]: ...

    def universe_history(self, *, project_slug: str, run_id: str) -> Sequence[Mapping[str, object]]: ...
