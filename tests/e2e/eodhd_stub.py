"""Deterministic EODHD-compatible server for Docker browser integration tests."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        request = urlparse(self.path)
        token = parse_qs(request.query).get("api_token", [""])[0]
        if token == "e2e-provider-500":
            self._reply(500, {"error": "simulated_provider_failure"})
            return
        if request.path == "/api/exchanges-list/":
            self._reply(200, [{"Code": "XETRA"}])
            return
        if request.path == "/api/exchange-symbol-list/XETRA":
            self._reply(
                200,
                [
                    {
                        "Code": "PORTFELL",
                        "Exchange": "XETRA",
                        "Name": "Portfell E2E ETF",
                        "Type": "ETF",
                        "Country": "IE",
                        "Currency": "EUR",
                        "Isin": "IE00E2E00001",
                    }
                ],
            )
            return
        self._reply(404, {"error": "not_found"})

    def _reply(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
