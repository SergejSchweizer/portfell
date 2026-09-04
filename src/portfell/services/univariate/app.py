"""Univariate-only application composition boundary."""

from __future__ import annotations

from fastapi import FastAPI

from portfell.modules.univariate.api import UnivariatePort, univariate_router


class UnivariateApplication:
    """Build a Univariate ASGI app from a persistence-backed port."""

    def __init__(self, service: UnivariatePort) -> None:
        self.service = service

    def create_app(self) -> FastAPI:
        app = FastAPI(title="Portfell Univariate", docs_url=None, redoc_url=None)
        app.include_router(univariate_router(self.service))

        @app.get("/health")
        def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
            return {"status": "ok", "module": "univariate"}

        return app
