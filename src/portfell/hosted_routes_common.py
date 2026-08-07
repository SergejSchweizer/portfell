"""Shared HTTP translation helpers for hosted route adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from portfell.hosted_api_errors import HostedApplicationError

JsonRow = dict[str, Any]


def call[ReturnT](operation: Callable[..., ReturnT], *args: Any, **kwargs: Any) -> ReturnT:
    """Translate one application error into the stable HTTP error envelope."""

    try:
        return operation(*args, **kwargs)
    except HostedApplicationError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error
