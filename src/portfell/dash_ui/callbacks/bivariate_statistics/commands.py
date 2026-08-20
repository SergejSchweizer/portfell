"""Logical command identity for Bivariate run starts."""

from __future__ import annotations

import hashlib


def start_command_key(*, project_slug: str, univariate_revision: str) -> str:
    """Return a stable logical start identity for duplicate callback convergence."""

    payload = f"bivariate|{project_slug}|{univariate_revision}".encode()
    return hashlib.sha256(payload).hexdigest()
