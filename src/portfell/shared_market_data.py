"""Canonical shared physical market-data store and active-project inventory.

Rows in this store are never project, user, credential, or run scoped.  A
project refers to shared data only through its selected full listing keys.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from portfell.table_io import JsonRow, read_json, read_rows, write_json, write_rows

_FORBIDDEN_FIELDS = frozenset(
    {"user_id", "project_id", "credential_id", "session_token", "run_id", "authorization"}
)
_DATASETS = frozenset({"quotes", "dividends", "splits"})
_SAFE_PATH = re.compile(r"[^A-Za-z0-9._-]+")


class SharedMarketDataError(ValueError):
    """Raised for invalid or unreadable canonical shared market data."""


@dataclass(frozen=True, order=True)
class SharedListingKey:
    """Complete provider listing identity used by physical shared files."""

    provider: str
    exchange: str
    code: str
    isin: str

    @classmethod
    def from_member_id(cls, member_id: str, *, provider: str = "eodhd") -> SharedListingKey:
        parts = member_id.split(":")
        if len(parts) != 3 or not all(parts):
            raise SharedMarketDataError("invalid_listing_member_id")
        return cls(provider, parts[1], parts[2], parts[0])

    @classmethod
    def from_row(cls, row: Mapping[str, Any], *, provider: str = "eodhd") -> SharedListingKey:
        return cls(
            str(row.get("provider", provider)),
            str(row.get("exchange", "")),
            str(row.get("code", "")),
            str(row.get("isin", "")),
        )

    def as_row(self) -> JsonRow:
        return {
            "provider": self.provider,
            "exchange": self.exchange,
            "code": self.code,
            "isin": self.isin,
        }


@dataclass(frozen=True)
class CoverageRecord:
    """Rebuildable metadata derived from one canonical listing/dataset file."""

    listing: SharedListingKey
    dataset_type: str
    first_business_date: str | None
    last_business_date: str | None
    row_count: int
    content_hash: str
    published_at_epoch: int
    schema_version: int = 1
    last_checked_date: str | None = None

    def row(self) -> JsonRow:
        return {
            **self.listing.as_row(),
            "dataset_type": self.dataset_type,
            "first_business_date": self.first_business_date,
            "last_business_date": self.last_business_date,
            "row_count": self.row_count,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "published_at_epoch": self.published_at_epoch,
            "last_checked_date": self.last_checked_date,
        }


class SharedMarketDataStore:
    """Immutable Parquet revisions per dataset and full listing identity."""

    def __init__(self, root: Path, *, before_replace: Callable[[Path], None] | None = None) -> None:
        self.root = root / "market-data"
        self._before_replace = before_replace
        self._catalog_lock = threading.RLock()

    def revision_path(
        self, dataset_type: str, listing: SharedListingKey, content_hash: str
    ) -> Path:
        self._validate_dataset(dataset_type)
        return (
            self.root
            / "revisions"
            / dataset_type
            / _path_part(listing.exchange)
            / f"{_path_part(listing.isin)}__{_path_part(listing.code)}"
            / f"{content_hash}.parquet"
        )

    def upsert(
        self, dataset_type: str, listing: SharedListingKey, rows: Iterable[Mapping[str, Any]]
    ) -> CoverageRecord:
        """Merge complete business keys, atomically publish, and update coverage."""

        with self._catalog_lock:
            catalog = self._read_catalog()
            record, _ = self._upsert_with_catalog(catalog, dataset_type, listing, rows)
            _atomic_write_json(
                self.root / "coverage.json", {"records": [catalog[key] for key in sorted(catalog)]}
            )
        return record

    def upsert_many(
        self,
        values: Iterable[tuple[str, SharedListingKey, Iterable[Mapping[str, Any]], str]],
    ) -> tuple[bool, ...]:
        """Publish a batch while reading and replacing the coverage catalogue once."""

        with self._catalog_lock:
            catalog = self._read_catalog()
            changed: list[bool] = []
            for dataset_type, listing, rows, last_checked_date in values:
                _, item_changed = self._upsert_with_catalog(
                    catalog,
                    dataset_type,
                    listing,
                    rows,
                    last_checked_date=last_checked_date,
                )
                changed.append(item_changed)
            if changed:
                _atomic_write_json(
                    self.root / "coverage.json",
                    {"records": [catalog[key] for key in sorted(catalog)]},
                )
        return tuple(changed)

    def _upsert_with_catalog(
        self,
        catalog: dict[str, JsonRow],
        dataset_type: str,
        listing: SharedListingKey,
        rows: Iterable[Mapping[str, Any]],
        *,
        last_checked_date: str | None = None,
    ) -> tuple[CoverageRecord, bool]:
        self._validate_dataset(dataset_type)
        key = _coverage_key_for(dataset_type, listing)
        existing_record = _record(catalog[key]) if key in catalog else None
        existing = (
            []
            if existing_record is None
            else self.read_revision(dataset_type, listing, existing_record.content_hash)
        )
        merged = {
            _business_key(dataset_type, row): _normalized_row(row, listing) for row in existing
        }
        for row in rows:
            normalized = _normalized_row(row, listing)
            merged[_business_key(dataset_type, normalized)] = normalized
        canonical = [merged[key] for key in sorted(merged)]
        record = _coverage(
            dataset_type,
            listing,
            canonical,
            published_at_epoch=0,
            last_checked_date=last_checked_date
            or (None if existing_record is None else existing_record.last_checked_date),
        )
        path = self.revision_path(dataset_type, listing, record.content_hash)
        if not path.exists():
            _atomic_write(path, canonical, self._before_replace)
        catalog[key] = record.row()
        changed = existing_record is None or record != existing_record
        return record, changed

    def read(self, dataset_type: str, listing: SharedListingKey) -> list[JsonRow]:
        record = next(
            (
                item
                for item in self.coverage()
                if item.dataset_type == dataset_type and item.listing == listing
            ),
            None,
        )
        if record is None:
            return []
        return self.read_revision(dataset_type, listing, record.content_hash)

    def read_revision(
        self, dataset_type: str, listing: SharedListingKey, content_hash: str
    ) -> list[JsonRow]:
        """Read one explicitly pinned immutable revision."""

        self._validate_dataset(dataset_type)
        path = self.revision_path(dataset_type, listing, content_hash)
        try:
            rows = read_rows(path)
        except Exception as error:
            raise SharedMarketDataError("shared_market_file_corrupt") from error
        if any(SharedListingKey.from_row(row) != listing for row in rows):
            raise SharedMarketDataError("shared_market_listing_identity_mismatch")
        if _hash(rows) != content_hash:
            raise SharedMarketDataError("shared_market_revision_hash_mismatch")
        return rows

    def coverage(self) -> tuple[CoverageRecord, ...]:
        return tuple(_record(row) for _, row in sorted(self._read_catalog().items()))

    def rebuild_coverage(self) -> tuple[CoverageRecord, ...]:
        records: list[CoverageRecord] = []
        current = {(item.dataset_type, item.listing): item for item in self.coverage()}
        for dataset in sorted(_DATASETS):
            for path in sorted((self.root / "revisions" / dataset).glob("*/*/*.parquet")):
                try:
                    rows = read_rows(path)
                except Exception as error:
                    raise SharedMarketDataError("shared_market_file_corrupt") from error
                if not rows:
                    continue
                listing = SharedListingKey.from_row(rows[0])
                active = current.get((dataset, listing))
                record = _coverage(
                    dataset,
                    listing,
                    rows,
                    published_at_epoch=0,
                    last_checked_date=None if active is None else active.last_checked_date,
                )
                if active is None or active.content_hash == record.content_hash:
                    records.append(record)
        _atomic_write_json(
            self.root / "coverage.json", {"records": [item.row() for item in records]}
        )
        return tuple(records)

    def _read_catalog(self) -> dict[str, JsonRow]:
        path = self.root / "coverage.json"
        if not path.exists():
            return {}
        try:
            values = cast(object, read_json(path).get("records", []))
            if not isinstance(values, list):
                raise ValueError
            catalog_rows = cast(list[object], values)
            mapping_values = [
                cast(Mapping[str, Any], row) for row in catalog_rows if isinstance(row, Mapping)
            ]
            records = [_record(row) for row in mapping_values]
            if len(records) != len(catalog_rows):
                raise ValueError("catalog records must be objects")
            return {_coverage_key(record): record.row() for record in records}
        except Exception as error:
            raise SharedMarketDataError("shared_market_coverage_catalog_corrupt") from error

    @staticmethod
    def _validate_dataset(dataset_type: str) -> None:
        if dataset_type not in _DATASETS:
            raise SharedMarketDataError("unsupported_shared_market_dataset")


def inventory_hash(items: Iterable[SharedListingKey]) -> str:
    return _hash([item.as_row() for item in sorted(items)])


def _normalized_row(row: Mapping[str, Any], listing: SharedListingKey) -> JsonRow:
    forbidden = _FORBIDDEN_FIELDS.intersection(row)
    if forbidden:
        raise SharedMarketDataError("forbidden_shared_market_fields")
    actual = SharedListingKey.from_row(row, provider=listing.provider)
    if actual != listing:
        raise SharedMarketDataError("shared_market_listing_identity_mismatch")
    return {key: row[key] for key in sorted(row)}


def _business_key(dataset_type: str, row: Mapping[str, Any]) -> str:
    if dataset_type == "quotes":
        values = (row.get("date"),)
    elif dataset_type == "dividends":
        event_id = row.get("event_id", row.get("id", row.get("source_id")))
        if event_id is not None and event_id != "":
            values = (event_id, row.get("payment_date", row.get("paymentDate", row.get("date"))))
        else:
            event_date = row.get("date", row.get("payment_date", row.get("paymentDate")))
            details = (
                row.get("declarationDate", ""),
                row.get("recordDate", ""),
                row.get("paymentDate", row.get("payment_date", "")),
                row.get("period", ""),
                row.get("unadjustedValue", row.get("value", "")),
            )
            values = (event_date, *(detail for detail in details if detail not in (None, "")))
    else:
        values = (row.get("date"), row.get("split_factor", row.get("ratio", row.get("split"))))
    if any(value is None or value == "" for value in values):
        raise SharedMarketDataError("shared_market_business_key_missing")
    return "\u001f".join(str(value) for value in values)


def _coverage(
    dataset: str,
    listing: SharedListingKey,
    rows: list[JsonRow],
    *,
    published_at_epoch: int,
    last_checked_date: str | None = None,
) -> CoverageRecord:
    dates = sorted(str(row.get("date") or row.get("payment_date") or "") for row in rows)
    dates = [value for value in dates if value]
    return CoverageRecord(
        listing,
        dataset,
        dates[0] if dates else None,
        dates[-1] if dates else None,
        len(rows),
        _hash(rows),
        published_at_epoch,
        last_checked_date=last_checked_date,
    )


def _record(row: Mapping[str, Any]) -> CoverageRecord:
    return CoverageRecord(
        SharedListingKey.from_row(row),
        str(row["dataset_type"]),
        _optional(row.get("first_business_date")),
        _optional(row.get("last_business_date")),
        int(row["row_count"]),
        str(row["content_hash"]),
        int(row.get("published_at_epoch", 0)),
        int(row.get("schema_version", 1)),
        _optional(row.get("last_checked_date")),
    )


def _coverage_key(record: CoverageRecord) -> str:
    return _coverage_key_for(record.dataset_type, record.listing)


def _coverage_key_for(dataset_type: str, listing: SharedListingKey) -> str:
    return ":".join(
        (
            dataset_type,
            listing.provider,
            listing.exchange,
            listing.code,
            listing.isin,
        )
    )


def _atomic_write(
    path: Path, rows: list[JsonRow], before_replace: Callable[[Path], None] | None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.{uuid.uuid4().hex}.tmp{path.suffix}")
    try:
        write_rows(temporary, rows)
        _fsync(temporary)
        if before_replace:
            before_replace(temporary)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_json(path: Path, value: JsonRow) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.{uuid.uuid4().hex}.tmp.json")
    try:
        write_json(temporary, value)
        _fsync(temporary)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _fsync(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _path_part(value: str) -> str:
    return _SAFE_PATH.sub("_", value)


def _optional(value: object) -> str | None:
    return str(value) if value else None
