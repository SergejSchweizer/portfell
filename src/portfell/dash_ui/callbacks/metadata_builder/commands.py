"""Idempotent logical command identities for Metadata Builder callbacks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping


def command_key(*, command: str, project_slug: str | None, payload: Mapping[str, object]) -> str:
    """Create a deterministic command key so duplicate callbacks converge server-side."""

    canonical = json.dumps(
        {"command": command, "project_slug": project_slug, "payload": dict(payload)},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()
