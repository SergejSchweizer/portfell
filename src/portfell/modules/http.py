"""HTTP helpers shared by the four feature routers only."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from portfell.app_services.research import ApplicationServiceError


def service_call[ReturnT](operation: Callable[..., ReturnT], *args: Any, **kwargs: Any) -> ReturnT:
    try:
        return operation(*args, **kwargs)
    except ApplicationServiceError as error:
        status = (
            404 if error.code.endswith("not_found") else 409 if "not_ready" in error.code else 422
        )
        raise HTTPException(status_code=status, detail={"code": error.code}) from error


def required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail={"code": f"{key}_required"})
    return value


def optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value.strip() else None
