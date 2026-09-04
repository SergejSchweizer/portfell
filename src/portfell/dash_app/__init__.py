"""Plotly Dash browser application for the four-stage Portfell workflow."""

from portfell.dash_app.app import create_dash_app, mount_dash
from portfell.dash_app.contracts import PAGE_SPECS, PageSpec

__all__ = ["PAGE_SPECS", "PageSpec", "create_dash_app", "mount_dash"]
