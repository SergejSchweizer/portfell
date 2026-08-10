"""D017 tenant-control and tenant-neutral payload-plane contracts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OWNERSHIP_MATRIX_PATH = REPOSITORY_ROOT / "docs" / "security" / "shared_data_plane.json"
FORBIDDEN_SHARED_PAYLOAD_FIELDS = frozenset(
    {"authorization", "credential_id", "project_id", "run_id", "session_token", "user_id"}
)
REQUIRED_SHARED_DATA_LICENSE_USES = (
    "cross-customer-storage",
    "derived-artifact-reuse",
    "retention-after-project-deletion",
    "service-credential-ingestion",
)
_REQUIRED_IDENTITIES = {
    "listing": ("provider", "exchange", "isin", "code"),
    "market_revision": ("dataset_type", "schema_version", "business_key_hash", "content_hash"),
    "analytical_artifact": (
        "input_revision_ids",
        "parameters_hash",
        "algorithm_version",
        "schema_version",
    ),
}


class DataPlaneContractError(ValueError):
    """Raised when the versioned D017 ownership matrix is invalid."""


@dataclass(frozen=True, order=True)
class FullListingIdentity:
    """Canonical physical listing identity independent of tenant ownership."""

    provider: str
    exchange: str
    isin: str
    code: str

    def __post_init__(self) -> None:
        if not all((self.provider, self.exchange, self.isin, self.code)):
            raise DataPlaneContractError("full_listing_identity_required")

    def row(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "exchange": self.exchange,
            "isin": self.isin,
            "code": self.code,
        }


class TenantControlPlane(Protocol):
    """Future tenant authority; shared payload presence cannot authorize reads."""

    def project_can_resolve(self, *, user_id: str, project_id: str, payload_id: str) -> bool:
        """Return whether an owned project may resolve one immutable payload reference."""

        ...


class SharedMarketStore(Protocol):
    """Future tenant-neutral immutable market revision store."""

    def read_revision(self, *, revision_id: str) -> bytes:
        """Read one immutable market revision by its trusted catalog identity."""

        ...


class SharedArtifactStore(Protocol):
    """Future tenant-neutral immutable analytical payload store."""

    def read_artifact(self, *, artifact_id: str) -> bytes:
        """Read one immutable analytical payload by its trusted catalog identity."""

        ...


class SharedCatalog(Protocol):
    """Future trusted catalog for resolving immutable payload identities."""

    def payload_exists(self, *, payload_id: str) -> bool:
        """Return whether a complete, readable immutable payload is cataloged."""

        ...


def load_ownership_matrix(path: Path = OWNERSHIP_MATRIX_PATH) -> dict[str, Any]:
    """Load the D017 machine-readable ownership matrix."""

    with path.open(encoding="utf-8") as matrix_file:
        payload = cast(object, json.load(matrix_file))
    if not isinstance(payload, dict):
        raise DataPlaneContractError("ownership_matrix_must_be_object")
    return cast(dict[str, Any], payload)


def validate_ownership_matrix(payload: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    """Return stable violations for D017 plane, identity, and authorization contracts."""

    matrix = payload or load_ownership_matrix()
    violations: list[str] = []
    if matrix.get("schema_version") != 1:
        violations.append("schema_version")
    planes = _mapping(matrix.get("planes"))
    if planes is None or set(planes) != {"tenant_control", "shared_payload"}:
        violations.append("planes")
    else:
        for name in ("tenant_control", "shared_payload"):
            plane = _mapping(planes.get(name))
            if plane is None or _string_list(plane.get("owns")) is None:
                violations.append(f"planes.{name}")
    forbidden = _string_list(matrix.get("forbidden_shared_payload_fields"))
    if forbidden is None or frozenset(forbidden) != FORBIDDEN_SHARED_PAYLOAD_FIELDS:
        violations.append("forbidden_shared_payload_fields")
    identities = _mapping(matrix.get("identities"))
    if identities is None:
        violations.append("identities")
    else:
        for identity_name, fields in _REQUIRED_IDENTITIES.items():
            identity_fields = _string_list(identities.get(identity_name))
            if identity_fields is None or tuple(identity_fields) != fields:
                violations.append(f"identities.{identity_name}")
    authorization = _mapping(matrix.get("authorization"))
    if (
        not isinstance(authorization, Mapping)
        or authorization.get("project_reference_required") is not True
    ):
        violations.append("authorization.project_reference_required")
    credential_role = matrix.get("shared_ingestion_credential_role")
    if credential_role != "operations-only":
        violations.append("shared_ingestion_credential_role")
    return tuple(violations)


def _mapping(value: object) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    raw_mapping = cast(Mapping[object, object], value)
    if not all(isinstance(key, str) for key in raw_mapping):
        return None
    return cast(Mapping[str, Any], raw_mapping)


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    raw_values = cast(list[object], value)
    if not all(isinstance(item, str) for item in raw_values):
        return None
    return cast(list[str], raw_values)
