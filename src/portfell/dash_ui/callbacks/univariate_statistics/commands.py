"""Logical command identity for Univariate run starts."""

from __future__ import annotations

import hashlib


def start_command_key(*, project_slug: str, upstream_revision: str) -> str:
    """Return a stable logical start identity for duplicate callback convergence."""

    payload = f"univariate|{project_slug}|{upstream_revision}".encode()
    return hashlib.sha256(payload).hexdigest()
