"""Durable local-workspace storage for the trusted single-user runtime."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import cast


class LocalWorkspaceStore:
    """Atomically persist non-secret local-workspace state in the shared volume."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> dict[str, object]:
        """Return the stored workspace payload, or an empty payload on first start."""

        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        try:
            payload = cast("object", json.loads(raw))
        except json.JSONDecodeError as error:
            raise ValueError("local workspace state is invalid") from error
        if not isinstance(payload, dict):
            raise ValueError("local workspace state has an invalid shape")
        return cast("dict[str, object]", payload)

    def save(self, payload: Mapping[str, object]) -> None:
        """Atomically replace the local workspace payload with owner-only permissions."""

        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with tempfile.NamedTemporaryFile(
            "w",
            dir=self._path.parent,
            encoding="utf-8",
            delete=False,
        ) as temporary:
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        temporary_path.chmod(0o600)
        temporary_path.replace(self._path)
