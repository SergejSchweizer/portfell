"""Redacted PostgreSQL connection construction for hosted operator commands."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class HostedDatabaseConnectionError(RuntimeError):
    """Raised when the externally managed database password file is unusable."""


def database_password(secret_name: str = "PORTFELL_DATABASE_PASSWORD_FILE") -> str | None:
    """Read a nonempty external password file without exposing its contents."""

    value = os.environ.get(secret_name)
    if value is None:
        return None
    try:
        password = Path(value).read_text(encoding="utf-8").strip()
    except OSError as error:
        raise HostedDatabaseConnectionError("database_password_file_unavailable") from error
    if not password:
        raise HostedDatabaseConnectionError("database_password_file_unavailable")
    return password


def connect(
    database_url: str, *, autocommit: bool, password_secret: str = "PORTFELL_DATABASE_PASSWORD_FILE"
) -> Any:
    """Connect with an optional externally managed password file."""

    import psycopg

    password = database_password(password_secret)
    parameters: dict[str, Any] = {"autocommit": autocommit}
    if password is not None:
        parameters["password"] = password
    return psycopg.connect(database_url, **parameters)
