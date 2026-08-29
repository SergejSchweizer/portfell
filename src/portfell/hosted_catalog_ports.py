"""Minimal PostgreSQL cursor contracts used by catalog migrations."""

from __future__ import annotations

from typing import Protocol


class CatalogResult(Protocol):
    def fetchone(self) -> tuple[str] | None: ...


class CatalogConnection(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> CatalogResult: ...
