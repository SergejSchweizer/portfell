"""Content-addressed, atomic filesystem publication for shared artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4

from portfell_contracts import ArtifactManifest, ArtifactStatus, Stage

_NAMESPACES = frozenset({"market", "univariate", "bivariate", "multivariate"})


class ArtifactStoreError(RuntimeError):
    """Safe, stable artifact-store failure."""


class ArtifactIdentityConflict(ArtifactStoreError):
    """The same immutable artifact ID was presented with different bytes."""


def _namespace(owner: Stage) -> str:
    if owner is Stage.GATEWAY:
        raise ArtifactStoreError("gateway_cannot_publish_artifacts")
    return "market" if owner is Stage.METADATA else owner.value


class ArtifactStore:
    """Publish and verify immutable artifacts below one configured root."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._publish_lock = Lock()
        self.root.mkdir(parents=True, exist_ok=True)
        for namespace in _NAMESPACES:
            (self.root / namespace).mkdir(mode=0o750, exist_ok=True)

    def publish_bytes(
        self,
        *,
        owner: Stage,
        artifact_id: str,
        schema_version: str,
        content: bytes,
        row_count: int,
    ) -> ArtifactManifest:
        """Atomically publish bytes and a manifest, or reuse identical bytes."""

        with self._publish_lock:
            return self._publish_bytes(
                owner=owner,
                artifact_id=artifact_id,
                schema_version=schema_version,
                content=content,
                row_count=row_count,
            )

    def _publish_bytes(
        self,
        *,
        owner: Stage,
        artifact_id: str,
        schema_version: str,
        content: bytes,
        row_count: int,
    ) -> ArtifactManifest:
        """Perform one serialized publication attempt."""

        if (
            not artifact_id
            or "/" in artifact_id
            or "\\" in artifact_id
            or artifact_id in {".", ".."}
        ):
            raise ArtifactStoreError("artifact_id_invalid")
        namespace = _namespace(owner)
        directory = self.root / namespace
        data_path = directory / f"{artifact_id}.bin"
        manifest_path = directory / f"{artifact_id}.manifest.json"
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if data_path.exists() or manifest_path.exists():
            if not data_path.is_file() or not manifest_path.is_file():
                raise ArtifactStoreError("artifact_existing_path_invalid")
            existing = self.read(owner=owner, artifact_id=artifact_id)
            if existing.content_hash != digest or data_path.read_bytes() != content:
                raise ArtifactIdentityConflict("artifact_identity_conflict")
            return existing

        published_at = datetime.now(UTC)
        manifest = ArtifactManifest(
            artifact_id=artifact_id,
            owner=owner,
            schema_version=schema_version,
            content_hash=digest,
            relative_path=f"{namespace}/{artifact_id}.bin",
            byte_size=len(content),
            row_count=row_count,
            status=ArtifactStatus.PUBLISHED,
            published_at=published_at,
        )
        self._atomic_write(data_path, content)
        self._atomic_write(
            manifest_path,
            json.dumps(manifest.to_document(), sort_keys=True, separators=(",", ":")).encode(),
        )
        return manifest

    def read(self, *, owner: Stage, artifact_id: str) -> ArtifactManifest:
        """Read and verify a published artifact manifest and its bytes."""

        namespace = _namespace(owner)
        directory = self.root / namespace
        manifest_path = directory / f"{artifact_id}.manifest.json"
        data_path = directory / f"{artifact_id}.bin"
        if not manifest_path.is_file() or not data_path.is_file():
            raise ArtifactStoreError("artifact_not_published")
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
        try:
            status = ArtifactStatus(str(document["status"]))
            manifest_owner = Stage(str(document["owner"]))
            published_at_raw = document.get("published_at")
            published_at = (
                datetime.fromisoformat(str(published_at_raw)) if published_at_raw else None
            )
            manifest = ArtifactManifest(
                artifact_id=str(document["artifact_id"]),
                owner=manifest_owner,
                schema_version=str(document["schema_version"]),
                content_hash=str(document["content_hash"]),
                relative_path=str(document["relative_path"]),
                byte_size=int(document["byte_size"]),
                row_count=int(document["row_count"]),
                status=status,
                published_at=published_at,
                contract_version=str(document["contract_version"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ArtifactStoreError("artifact_manifest_invalid") from error
        if manifest.owner is not owner or manifest.status is not ArtifactStatus.PUBLISHED:
            raise ArtifactStoreError("artifact_owner_or_status_mismatch")
        if (
            manifest.artifact_id != artifact_id
            or manifest.relative_path != f"{namespace}/{artifact_id}.bin"
        ):
            raise ArtifactStoreError("artifact_manifest_path_mismatch")
        payload = data_path.read_bytes()
        if len(payload) != manifest.byte_size:
            raise ArtifactStoreError("artifact_size_mismatch")
        if f"sha256:{hashlib.sha256(payload).hexdigest()}" != manifest.content_hash:
            raise ArtifactStoreError("artifact_hash_mismatch")
        return manifest

    def _atomic_write(self, destination: Path, content: bytes) -> None:
        """Write in the same directory, fsync, then atomically replace."""

        if destination.resolve().parent != self.root / destination.parent.name:
            raise ArtifactStoreError("artifact_path_escape")
        fd, temporary = tempfile.mkstemp(
            prefix=f".{uuid4().hex}.", suffix=".part", dir=destination.parent
        )
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
            try:
                directory_fd = os.open(destination.parent, os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                pass
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
