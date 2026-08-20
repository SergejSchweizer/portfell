"""Temporary standalone Dash runtime used until the FastAPI cutover."""

from portfell.dash_ui.runtime.app import create_dash_app

__all__ = ["create_dash_app"]
