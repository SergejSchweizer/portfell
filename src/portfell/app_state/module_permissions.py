"""Declarative least-privilege rights for module roles."""

from __future__ import annotations

from typing import Final

MODULE_ROLES: Final[dict[str, str]] = {
    "gateway": "portfell_gateway",
    "metadata": "portfell_metadata",
    "univariate": "portfell_univariate",
    "bivariate": "portfell_bivariate",
    "multivariate": "portfell_multivariate",
}

MODULE_WRITE_SCHEMAS: Final[dict[str, str]] = {
    "gateway": "workflow",
    "metadata": "metadata",
    "univariate": "univariate",
    "bivariate": "bivariate",
    "multivariate": "multivariate",
}


def role_for_module(module: str) -> str:
    try:
        return MODULE_ROLES[module]
    except KeyError as error:
        raise ValueError("unknown_module") from error


def can_write_schema(module: str, schema: str) -> bool:
    return MODULE_WRITE_SCHEMAS.get(module) == schema
