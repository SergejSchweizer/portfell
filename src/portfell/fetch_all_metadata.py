"""Fetch the full EODHD listing metadata universe into one reference artifact."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast

from portfell.http import EodhdHttpError
from portfell.paths import LakePaths
from portfell.schemas import validate_rows
from portfell.table_io import JsonRow, write_json, write_rows


class EodhdJsonClient(Protocol):
    """Protocol for EODHD JSON clients used by this module."""

    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | float] | None = None,
    ) -> object: ...


@dataclass(frozen=True)
class AllMetadataFetchResult:
    """Result of a full EODHD listing metadata refresh."""

    rows: tuple[JsonRow, ...]
    requested_exchanges: tuple[str, ...]
    skipped_exchanges: tuple[str, ...]


def fetch_all_metadata(
    client: EodhdJsonClient,
    *,
    exchange_codes: Sequence[str] = (),
    known_exchange_codes: Sequence[str] = (),
    include_delisted: bool = False,
    on_progress: Callable[[int, int, int], None] | None = None,
) -> AllMetadataFetchResult:
    """Fetch and normalize missing EODHD listing metadata with ISINs."""
    explicit_exchanges = bool(exchange_codes)
    available_exchanges = tuple(exchange_codes) or _fetch_exchange_codes(client)
    known_exchanges = set(known_exchange_codes)
    resolved_exchanges = (
        available_exchanges
        if explicit_exchanges
        else tuple(exchange for exchange in available_exchanges if exchange not in known_exchanges)
    )
    fetched_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    rows: list[JsonRow] = []
    skipped_exchanges: list[str] = []
    if on_progress is not None:
        on_progress(0, len(resolved_exchanges), 0)
    for completed, exchange in enumerate(resolved_exchanges, start=1):
        try:
            payload = client.get_json(
                f"/exchange-symbol-list/{exchange}",
                {"fmt": "json", "delisted": 1 if include_delisted else 0},
            )
        except EodhdHttpError as error:
            if explicit_exchanges or error.status_code not in {403, 404}:
                raise
            skipped_exchanges.append(exchange)
            if on_progress is not None:
                on_progress(completed, len(resolved_exchanges), len(skipped_exchanges))
            continue
        rows.extend(
            _normalize_listing(row, source_exchange=exchange, fetched_at=fetched_at)
            for row in _payload_rows(payload)
            if _valid_isin(row.get("Isin", row.get("isin", "")))
        )
        if on_progress is not None:
            on_progress(completed, len(resolved_exchanges), len(skipped_exchanges))
    return AllMetadataFetchResult(
        rows=tuple(
            sorted(rows, key=lambda row: (str(row["isin"]), str(row["exchange"]), str(row["code"])))
        ),
        requested_exchanges=resolved_exchanges,
        skipped_exchanges=tuple(skipped_exchanges),
    )


def write_all_metadata(
    paths: LakePaths,
    rows: Sequence[Mapping[str, Any]],
    *,
    completed_exchanges: Sequence[str] = (),
) -> list[JsonRow]:
    """Write the reference all-ISIN dataset and manifest."""
    normalized = [dict(row) for row in rows if _valid_isin(row.get("isin", ""))]
    validate_rows("all_isins", normalized)
    write_rows(paths.all_isins(), normalized)
    write_json(
        paths.all_isins_manifest(),
        {
            "dataset": "all_isins",
            "path": str(paths.all_isins()),
            "row_count": len(normalized),
            "completed_exchanges": sorted(set(completed_exchanges)),
            "updated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        },
    )
    return normalized


def _fetch_exchange_codes(client: EodhdJsonClient) -> tuple[str, ...]:
    payload = client.get_json("/exchanges-list/", {"fmt": "json"})
    codes: list[str] = []
    for row in _payload_rows(payload):
        code = str(row.get("Code", row.get("code", ""))).strip()
        if code:
            codes.append(code)
    return tuple(sorted(set(codes)))


def _payload_rows(payload: object) -> list[Mapping[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("EODHD payload must be a JSON list")
    rows: list[Mapping[str, Any]] = []
    for item in cast(list[object], payload):
        if not isinstance(item, dict):
            raise ValueError("EODHD payload rows must be objects")
        rows.append(cast(Mapping[str, Any], item))
    return rows


def _normalize_listing(
    raw: Mapping[str, Any],
    *,
    source_exchange: str,
    fetched_at: str,
) -> JsonRow:
    exchange = (
        str(raw.get("Exchange", raw.get("exchange", source_exchange))).strip() or source_exchange
    )
    name = str(raw.get("Name", raw.get("name", ""))).strip()
    return {
        "isin": _text(raw.get("Isin", raw.get("isin", ""))),
        "exchange": exchange,
        "code": _text(raw.get("Code", raw.get("code", ""))),
        "name": name,
        "instrument_type": _text(raw.get("Type", raw.get("type", ""))),
        "country": _text(raw.get("Country", raw.get("country", ""))),
        "currency": _text(raw.get("Currency", raw.get("currency", ""))),
        "source_exchange": source_exchange,
        "fetched_at": fetched_at,
    }


def _valid_isin(value: object) -> bool:
    return _text(value).casefold() not in {"", "none", "null"}


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()
