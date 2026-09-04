"""Public routing shell with no analytical capabilities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from fastapi import FastAPI


@dataclass(frozen=True, slots=True)
class ModuleHealth:
    module: str
    status: str
    detail: str | None = None

    def to_document(self) -> dict[str, str]:
        result = {"module": self.module, "status": self.status}
        if self.detail is not None:
            result["detail"] = self.detail
        return result


WorkflowReader = Callable[[], Mapping[str, object]]


class GatewayApplication:
    """Compose already-built module ASGI apps without importing their logic."""

    def __init__(
        self,
        *,
        modules: Mapping[str, FastAPI],
        workflow_reader: WorkflowReader,
    ) -> None:
        expected = {"metadata", "univariate", "bivariate", "multivariate"}
        if set(modules) != expected:
            raise ValueError("gateway_requires_exactly_four_modules")
        self.modules = dict(modules)
        self.workflow_reader = workflow_reader

    def create_app(self) -> FastAPI:
        app = FastAPI(title="Portfell Gateway", docs_url=None, redoc_url=None)
        for module_name in ("metadata", "univariate", "bivariate", "multivariate"):
            app.mount(f"/{module_name}", self.modules[module_name])

        @app.get("/health")
        def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
            return {"status": "ok", "module": "gateway"}

        @app.get("/api/workflow")
        def workflow() -> Mapping[str, object]:  # pyright: ignore[reportUnusedFunction]
            return self.workflow_reader()

        return app
