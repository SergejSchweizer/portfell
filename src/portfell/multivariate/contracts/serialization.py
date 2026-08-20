"""Canonical finite JSON serialization for Multivariate identities and evidence."""

from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Mapping, Sequence
from enum import Enum

_FORBIDDEN_KEY_FRAGMENTS = ("secret", "password", "token_file", "private_key", "filesystem_path")


def _primitive(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical serialization rejects NaN/Inf")
        return value
    if isinstance(value, Enum):
        return _primitive(value.value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _primitive(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical mappings require string keys")
            lowered = key.lower()
            if any(fragment in lowered for fragment in _FORBIDDEN_KEY_FRAGMENTS):
                raise ValueError(f"forbidden public evidence key: {key}")
            result[key] = _primitive(item)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_primitive(item) for item in value]
    raise TypeError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_json(value: object) -> str:
    """Serialize supported values with stable ordering and no non-finite numbers."""

    return json.dumps(
        _primitive(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=True,
    )
