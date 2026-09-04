"""Single-process composition root for the four Portfell modules.

This module owns only wiring. Module business logic remains behind the typed
facades in :mod:`portfell.modules.runtime`; no calculation or persistence
policy belongs here.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import FastAPI

from portfell.modules import build_module_registry
from portfell.modules.bivariate import bivariate_router
from portfell.modules.metadata import metadata_router
from portfell.modules.multivariate import multivariate_router
from portfell.modules.runtime import ModuleRegistry
from portfell.modules.univariate import univariate_router


def compose_modules(service: object) -> ModuleRegistry:
    """Create the restricted in-process module registry once per application."""

    return build_module_registry(service)


def mount_module_routes(application: FastAPI, modules: ModuleRegistry) -> None:
    """Mount each module's REST boundary on the shared Application process."""

    application.include_router(metadata_router(cast(Any, modules.metadata)))
    application.include_router(univariate_router(cast(Any, modules.univariate)))
    application.include_router(bivariate_router(cast(Any, modules.bivariate)))
    application.include_router(multivariate_router(cast(Any, modules.multivariate)))


__all__ = ["compose_modules", "mount_module_routes"]
