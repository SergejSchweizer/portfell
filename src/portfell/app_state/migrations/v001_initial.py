"""Initial clean single-workspace application-state migration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from portfell.app_state.schema import V1_DESTRUCTIVE_DOWN_SQL, V1_SCHEMA_SQL


@dataclass(frozen=True)
class AppStateMigration:
    """One immutable application-state migration declaration."""

    version: int
    name: str
    sql: str
    destructive_down_sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


MIGRATION_V001 = AppStateMigration(
    version=1,
    name="clean_app_state_v1",
    sql=V1_SCHEMA_SQL,
    destructive_down_sql=V1_DESTRUCTIVE_DOWN_SQL,
)
