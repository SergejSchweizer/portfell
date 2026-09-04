"""Separate read/write protocols for owner-specific PostgreSQL hand-offs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from portfell_contracts import (
    ArtifactManifest,
    BivariateRunId,
    MetadataUniverseId,
    MultivariateRunId,
    UnivariateRunId,
    UnivariateSelectionId,
)


class MetadataWriter(Protocol):
    def publish_universe(self, universe_id: MetadataUniverseId, member_count: int) -> None: ...


class MetadataReader(Protocol):
    def read_universe(self, universe_id: MetadataUniverseId) -> Mapping[str, object]: ...


class UnivariateWriter(Protocol):
    def publish_run(self, run_id: UnivariateRunId, universe_id: MetadataUniverseId) -> None: ...

    def publish_selection(
        self, selection_id: UnivariateSelectionId, run_id: UnivariateRunId, member_count: int
    ) -> None: ...


class UnivariateReader(Protocol):
    def read_selection_members(self, selection_id: UnivariateSelectionId) -> Sequence[str]: ...


class BivariateWriter(Protocol):
    def publish_run(self, run_id: BivariateRunId, selection_id: UnivariateSelectionId) -> None: ...


class BivariateReader(Protocol):
    def read_artifacts(self, run_id: BivariateRunId) -> Sequence[ArtifactManifest]: ...


class MultivariateWriter(Protocol):
    def publish_run(self, run_id: MultivariateRunId, bivariate_run_id: BivariateRunId) -> None: ...
