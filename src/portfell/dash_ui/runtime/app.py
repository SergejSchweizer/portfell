"""Temporary presentation-only Dash process.

The temporary process deliberately receives only the hosted API base URL. It is
removed when Dash is mounted into the Python application during the production
cutover.
"""

from __future__ import annotations

import os

from dash import Dash, html, page_container

from portfell.dash_ui.core.routes import TEMPORARY_DASH_PREFIX


def create_dash_app() -> Dash:
    """Create a side-effect-free Dash application at the temporary `/dash/` prefix."""

    prefix = f"{TEMPORARY_DASH_PREFIX}/"
    app = Dash(
        __name__,
        use_pages=True,
        pages_folder="",
        requests_pathname_prefix=prefix,
        routes_pathname_prefix=prefix,
        suppress_callback_exceptions=False,
        title="Portfell",
    )
    app.layout = html.Main(
        [
            html.H1("Portfell"),
            html.Div(page_container, id="dash-page-region"),
        ],
        id="dash-runtime-root",
    )
    return app


def main() -> None:
    """Run the temporary container entrypoint."""

    host = os.environ.get("PORTFELL_DASH_HOST", "0.0.0.0")
    port = int(os.environ.get("PORTFELL_DASH_PORT", "8050"))
    create_dash_app().run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
