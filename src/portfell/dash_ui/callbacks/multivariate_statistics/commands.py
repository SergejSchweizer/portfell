"""Idempotent Multivariate optimizer command identities."""

from __future__ import annotations

import hashlib

from portfell.multivariate.contracts.serialization import canonical_json
from portfell.multivariate.contracts.settings import MultivariateOptimizationSettings


def optimizer_command_key(
    *,
    project_slug: str,
    bivariate_revision: str,
    settings: MultivariateOptimizationSettings,
) -> str:
    """Create one stable logical start key for duplicate Dash callback delivery."""

    return hashlib.sha256(
        canonical_json(
            {
                "stage": "multivariate_statistics",
                "project_slug": project_slug,
                "bivariate_revision": bivariate_revision,
                "settings": settings,
            }
        ).encode()
    ).hexdigest()
