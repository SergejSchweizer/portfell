from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from portfell.hosted_api import HostedApiState, create_app
from portfell.hosted_api_errors import HOSTED_ERROR_CODES
from portfell.hosted_local_test_composition import local_test_services

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = REPOSITORY_ROOT / "docs" / "hosted_api_openapi.snapshot.json"
HTTP_METHODS = frozenset({"delete", "get", "patch", "post", "put"})


def _normalized_openapi() -> dict[str, object]:
    state = HostedApiState()
    specification = create_app(state, services=local_test_services(state)).openapi()
    paths = cast("dict[str, dict[str, dict[str, Any]]]", specification["paths"])
    return {
        "components": {"schemas": specification.get("components", {}).get("schemas", {})},
        "paths": {
            path: {
                method: {
                    key: operation[key]
                    for key in ("parameters", "requestBody", "responses")
                    if key in operation
                }
                for method, operation in sorted(item.items())
                if method in HTTP_METHODS
            }
            for path, item in sorted(paths.items())
        },
    }


def _operation_inventory(normalized: dict[str, object]) -> list[str]:
    paths = cast("dict[str, dict[str, dict[str, Any]]]", normalized["paths"])
    return [
        f"{method.upper()} {path} {'/'.join(sorted(operation['responses']))}"
        for path, item in paths.items()
        for method, operation in item.items()
    ]


def test_hosted_api_matches_normalized_openapi_snapshot() -> None:
    snapshot = cast("dict[str, Any]", json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8")))
    normalized = _normalized_openapi()
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()

    assert hashlib.sha256(canonical).hexdigest() == snapshot["normalized_sha256"]
    assert _operation_inventory(normalized) == snapshot["operations"]
    assert sorted(HOSTED_ERROR_CODES) == snapshot["error_codes"]
