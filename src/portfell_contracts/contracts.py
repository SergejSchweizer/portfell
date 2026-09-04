"""Stable, serializable stage-neutral workflow contracts.

The types in this module intentionally have no dependencies outside Python's
standard library.  A schema version is required on every serialized DTO so a
consumer cannot silently accept a newer incompatible document.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Final, NewType

MetadataUniverseId = NewType("MetadataUniverseId", str)
UnivariateRunId = NewType("UnivariateRunId", str)
UnivariateSelectionId = NewType("UnivariateSelectionId", str)
BivariateRunId = NewType("BivariateRunId", str)
MultivariateRunId = NewType("MultivariateRunId", str)

type SchemaVersion = str
type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonDocument = dict[str, JsonValue]

CONTRACT_VERSION: Final[str] = "1"
_SENSITIVE_CONTEXT_KEYS: Final[frozenset[str]] = frozenset(
    {"password", "token", "secret", "credential", "dsn", "sql", "path", "stack"}
)


class Stage(StrEnum):
    GATEWAY = "gateway"
    METADATA = "metadata"
    UNIVARIATE = "univariate"
    BIVARIATE = "bivariate"
    MULTIVARIATE = "multivariate"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactStatus(StrEnum):
    STAGED = "staged"
    PUBLISHED = "published"
    INVALID = "invalid"


def _version(value: str) -> str:
    if value != CONTRACT_VERSION:
        raise ValueError(f"unsupported contract version: {value!r}")
    return value


def _text(value: str, field: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{field} must be a non-empty trimmed string")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    """Immutable metadata needed to verify a published shared artifact."""

    artifact_id: str
    owner: Stage
    schema_version: SchemaVersion
    content_hash: str
    relative_path: str
    byte_size: int
    row_count: int
    status: ArtifactStatus = ArtifactStatus.PUBLISHED
    contract_version: SchemaVersion = CONTRACT_VERSION

    def __post_init__(self) -> None:
        _version(self.contract_version)
        _text(self.artifact_id, "artifact_id")
        _text(self.content_hash, "content_hash")
        _text(self.schema_version, "schema_version")
        if self.byte_size < 0 or self.row_count < 0:
            raise ValueError("byte_size and row_count must be non-negative")
        path = PurePosixPath(self.relative_path)
        if path.is_absolute() or ".." in path.parts or not self.relative_path:
            raise ValueError("relative_path must remain within the data-share root")

    def to_document(self) -> JsonDocument:
        return {
            "artifact_id": self.artifact_id,
            "byte_size": self.byte_size,
            "content_hash": self.content_hash,
            "contract_version": self.contract_version,
            "owner": self.owner.value,
            "relative_path": self.relative_path,
            "row_count": self.row_count,
            "schema_version": self.schema_version,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class JobProgress:
    """Restart-safe progress projection for a stage job."""

    stage: Stage
    status: JobStatus
    phase: str
    current: int = 0
    total: int | None = None
    contract_version: SchemaVersion = CONTRACT_VERSION

    def __post_init__(self) -> None:
        _version(self.contract_version)
        _text(self.phase, "phase")
        if self.current < 0 or (self.total is not None and self.total < 0):
            raise ValueError("progress values must be non-negative")
        if self.total is not None and self.current > self.total:
            raise ValueError("current progress cannot exceed total")

    def to_document(self) -> JsonDocument:
        return {
            "contract_version": self.contract_version,
            "current": self.current,
            "phase": self.phase,
            "stage": self.stage.value,
            "status": self.status.value,
            "total": self.total,
        }


@dataclass(frozen=True, slots=True)
class PublicError:
    """Safe error envelope; implementation details never cross a boundary."""

    code: str
    message: str
    context: tuple[tuple[str, JsonScalar], ...] = ()
    contract_version: SchemaVersion = CONTRACT_VERSION

    def __post_init__(self) -> None:
        _version(self.contract_version)
        _text(self.code, "code")
        _text(self.message, "message")
        for key, value in self.context:
            _text(key, "context key")
            if key.lower() in _SENSITIVE_CONTEXT_KEYS or any(
                marker in key.lower() for marker in ("password", "token", "secret", "sql", "path")
            ):
                raise ValueError("sensitive context is not public")
            if not isinstance(value, (str, int, float, bool)) and value is not None:
                raise ValueError("context values must be JSON scalars")

    def to_document(self) -> JsonDocument:
        return {
            "code": self.code,
            "context": {key: value for key, value in self.context},
            "contract_version": self.contract_version,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class WorkflowProjection:
    """Small gateway projection; it carries IDs and counts, never analytical rows."""

    metadata_universe_id: MetadataUniverseId | None = None
    univariate_run_id: UnivariateRunId | None = None
    univariate_selection_id: UnivariateSelectionId | None = None
    bivariate_run_id: BivariateRunId | None = None
    multivariate_run_id: MultivariateRunId | None = None
    metadata_count: int | None = None
    univariate_count: int | None = None
    bivariate_candidate_pairs: int | None = None
    status: JobStatus | None = None
    contract_version: SchemaVersion = CONTRACT_VERSION

    def __post_init__(self) -> None:
        _version(self.contract_version)
        counts = (
            self.metadata_count,
            self.univariate_count,
            self.bivariate_candidate_pairs,
        )
        if any(count is not None and count < 0 for count in counts):
            raise ValueError("projection counts must be non-negative")

    def to_document(self) -> JsonDocument:
        return {
            "bivariate_candidate_pairs": self.bivariate_candidate_pairs,
            "bivariate_run_id": self.bivariate_run_id,
            "contract_version": self.contract_version,
            "metadata_count": self.metadata_count,
            "metadata_universe_id": self.metadata_universe_id,
            "multivariate_run_id": self.multivariate_run_id,
            "status": self.status.value if self.status else None,
            "univariate_count": self.univariate_count,
            "univariate_run_id": self.univariate_run_id,
            "univariate_selection_id": self.univariate_selection_id,
        }
