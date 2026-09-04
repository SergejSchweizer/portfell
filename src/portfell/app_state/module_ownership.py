"""Static ownership matrix used by migrations and repository adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

MODULE_SCHEMAS: Final[Mapping[str, str]] = {
    "gateway": "workflow",
    "metadata": "metadata",
    "univariate": "univariate",
    "bivariate": "bivariate",
    "multivariate": "multivariate",
}

MODULE_TABLES: Final[Mapping[str, tuple[str, ...]]] = {
    "gateway": ("stage_commands",),
    "metadata": ("universes",),
    "univariate": ("runs", "selections"),
    "bivariate": ("runs",),
    "multivariate": ("runs",),
}


def owner_for_schema(schema: str) -> str:
    """Return the module owning *schema*, rejecting unknown schemas."""

    for module, owned_schema in MODULE_SCHEMAS.items():
        if owned_schema == schema:
            return module
    raise ValueError("unknown module schema")
