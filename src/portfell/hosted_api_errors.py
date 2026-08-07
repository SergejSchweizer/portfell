"""FastAPI-free errors raised by hosted application services."""

from __future__ import annotations

HOSTED_ERROR_CODES = frozenset(
    {
        "credential_not_found",
        "eodhd_credential_required",
        "eodhd_key_rejected",
        "eodhd_key_required",
        "eodhd_metadata_invalid_response",
        "eodhd_metadata_unavailable",
        "invalid_limit",
        "invalid_offset",
        "metadata_fetch_failed",
        "metadata_filter_empty",
        "metadata_filter_manifest_invalid",
        "metadata_filter_required",
        "metadata_run_not_found",
        "metadata_selection_required",
        "not_found",
        "quote_run_incomplete",
        "scoped_quote_rows_unavailable",
    }
)


class HostedApplicationError(RuntimeError):
    """A stable application error translated to HTTP by route adapters."""

    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code


class HostedRuntimeError(RuntimeError):
    """A normalized failure from a concrete hosted runtime adapter."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
