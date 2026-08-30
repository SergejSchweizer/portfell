"""Typed, redacted errors for clean application-state persistence."""

from __future__ import annotations


class AppStateError(RuntimeError):
    """Public application-state persistence failure with a stable code only."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


APP_STATE_CONFLICT = "app_state_conflict"
APP_STATE_NOT_FOUND = "app_state_not_found"
APP_STATE_PERSISTENCE_FAILED = "app_state_persistence_failed"
APP_STATE_INVALID_TRANSITION = "app_state_invalid_transition"
