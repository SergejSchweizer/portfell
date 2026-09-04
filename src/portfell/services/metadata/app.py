"""Metadata-only application composition boundary.

The process owns the metadata router and health endpoint. It receives a
MetadataPort implementation from its adapter and never imports another
analytical stage.
"""

from __future__ import annotations

from fastapi import FastAPI

from portfell.modules.metadata.api import MetadataPort, metadata_router


class MetadataApplication:
    """Build the independently runnable Metadata ASGI application."""

    def __init__(self, service: MetadataPort) -> None:
        self.service = service

    def create_app(self) -> FastAPI:
        app = FastAPI(title="Portfell Metadata", docs_url=None, redoc_url=None)
        app.include_router(metadata_router(self.service))

        @app.get("/health")
        def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
            return {"status": "ok", "module": "metadata"}

        return app
