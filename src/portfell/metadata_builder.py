"""Metadata-based ISIN selection from the all-ISIN reference dataset."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from portfell.paths import LakePaths
from portfell.schemas import validate_rows
from portfell.selection_filters import Predicate, filter_rows, selection_id
from portfell.table_io import JsonRow, read_rows, write_json, write_rows


def run_metadata_builder(
    paths: LakePaths,
    predicates: Sequence[Predicate],
    *,
    name: str | None = None,
) -> dict[str, Any]:
    """Filter the reference all-ISIN dataset by metadata predicates."""
    source_rows = read_rows(paths.all_isins())
    selected_rows = filter_rows(source_rows, predicates)
    resolved_selection_id = selection_id("metadata_builder", name, predicates)
    write_metadata_selection(
        paths,
        resolved_selection_id,
        selected_rows,
        predicates=predicates,
        source_path=str(paths.all_isins()),
    )
    return {
        "input_rows": len(source_rows),
        "selected_rows": len(selected_rows),
        "selection_id": resolved_selection_id,
        "selection_path": str(paths.metadata_builder_isins(resolved_selection_id)),
    }


def write_metadata_selection(
    paths: LakePaths,
    selection_id_value: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    predicates: Sequence[Predicate],
    source_path: str,
) -> list[JsonRow]:
    """Write a metadata-builder selection and its manifest."""
    selection_rows = [_selection_row(selection_id_value, row) for row in rows]
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    validate_rows("isin_selection", selection_rows)
    write_rows(paths.metadata_builder_isins(selection_id_value), selection_rows)
    write_json(
        paths.metadata_builder_manifest(selection_id_value),
        {
            "module": "metadata_builder",
            "selection_id": selection_id_value,
            "source_path": source_path,
            "row_count": len(selection_rows),
            "predicates": [predicate.as_text() for predicate in predicates],
            "created_at": created_at,
        },
    )
    write_json(
        paths.current_metadata_builder_selection(),
        {
            "selection_id": selection_id_value,
            "selection_path": str(paths.metadata_builder_isins(selection_id_value)),
            "manifest_path": str(paths.metadata_builder_manifest(selection_id_value)),
            "updated_at": created_at,
        },
    )
    return selection_rows


def _selection_row(selection_id_value: str, row: Mapping[str, Any]) -> JsonRow:
    return {
        "selection_id": selection_id_value,
        "isin": str(row["isin"]),
        "exchange": str(row["exchange"]),
        "code": str(row["code"]),
        "name": str(row.get("name", "")),
        "source_module": "metadata_builder",
    }
