"""Multivariate-only application composition boundary."""

from __future__ import annotations

from fastapi import FastAPI

from portfell.modules.multivariate.api import MultivariatePort, multivariate_router


class MultivariateApplication:
    """Build a Multivariate ASGI app from a persistence-backed port."""

    def __init__(self, service: MultivariatePort) -> None:
        self.service = service

    def create_app(self) -> FastAPI:
        app = FastAPI(title="Portfell Multivariate", docs_url=None, redoc_url=None)
        app.include_router(multivariate_router(self.service))

        @app.get("/health")
        def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
            return {"status": "ok", "module": "multivariate"}

        return app
