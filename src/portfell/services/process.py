"""Minimal process entry point used by the modular Compose profile.

Each process has an explicit module identity and health surface. Feature
routers are injected by the deployment adapter in later extraction PRs; there
is deliberately no monolith fallback command here.
"""

from __future__ import annotations

import sys

import uvicorn
from fastapi import FastAPI

MODULES = frozenset({"gateway", "metadata", "univariate", "bivariate", "multivariate"})


def create_process_app(module: str) -> FastAPI:
    if module not in MODULES:
        raise ValueError("unknown_process_module")
    app = FastAPI(title=f"Portfell {module}", docs_url=None, redoc_url=None)

    @app.get("/health")
    def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok", "module": module}

    return app


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in MODULES:
        raise SystemExit(
            "usage: python -m portfell.services.process "
            "<gateway|metadata|univariate|bivariate|multivariate>"
        )
    uvicorn.run(create_process_app(sys.argv[1]), host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
