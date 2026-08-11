"""Worker-owned, atomically published shared metadata catalogue."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterable, Mapping
from pathlib import Path

from portfell.schemas import validate_rows
from portfell.table_io import JsonRow, read_rows, write_rows


class SharedMetadataCatalog:
    """Publish the one canonical metadata catalogue without tenant data."""

    def __init__(self, root: Path) -> None:
        self.path = root / "market-data" / "metadata" / "current.parquet"

    def read(self) -> tuple[JsonRow, ...]:
        return tuple(read_rows(self.path))

    def publish(self, rows: Iterable[Mapping[str, object]]) -> tuple[JsonRow, ...]:
        """Validate and atomically replace the current immutable catalogue view."""

        canonical = tuple(
            sorted(
                (dict(row) for row in rows),
                key=lambda row: (
                    str(row["isin"]),
                    str(row["exchange"]),
                    str(row["code"]),
                ),
            )
        )
        validate_rows("all_isins", canonical)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.stem}.{uuid.uuid4().hex}.parquet")
        try:
            write_rows(temporary, canonical)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        return canonical
