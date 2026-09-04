"""Dependency-light contracts shared by the Portfell analytical stages.

This package deliberately contains only standard-library value objects.  It is
safe to import from a worker, API adapter, or browser composition layer without
pulling in a database driver or numerical stack.
"""

from .contracts import (
    ArtifactManifest,
    ArtifactStatus,
    BivariateRunId,
    JobProgress,
    JobStatus,
    MetadataUniverseId,
    MultivariateRunId,
    PublicError,
    SchemaVersion,
    Stage,
    UnivariateRunId,
    UnivariateSelectionId,
    WorkflowProjection,
)

__all__ = [
    "ArtifactManifest",
    "ArtifactStatus",
    "BivariateRunId",
    "JobProgress",
    "JobStatus",
    "MetadataUniverseId",
    "MultivariateRunId",
    "PublicError",
    "SchemaVersion",
    "Stage",
    "UnivariateRunId",
    "UnivariateSelectionId",
    "WorkflowProjection",
]
