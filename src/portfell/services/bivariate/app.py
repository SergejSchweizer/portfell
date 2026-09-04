"""Bivariate-only application composition boundary."""

from __future__ import annotations

from fastapi import FastAPI

from portfell.modules.bivariate.api import BivariatePort, bivariate_router


class BivariateApplication:
    """Build a Bivariate ASGI app from a persistence-backed port."""

    def __init__(self, service: BivariatePort) -> None:
        self.service = service

    def create_app(self) -> FastAPI:
        app = FastAPI(title="Portfell Bivariate", docs_url=None, redoc_url=None)
        app.include_router(bivariate_router(self.service))

        @app.get("/health")
        def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
            return {"status": "ok", "module": "bivariate"}

        return app
