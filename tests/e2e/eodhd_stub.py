"""Deterministic EODHD-compatible server for Docker browser integration tests."""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

_LISTINGS = tuple(
    {
        "Code": f"PF{index:02d}",
        "Exchange": "XETRA",
        "Name": f"Portfell {index} Monthly Income UCITS ETF",
        "Type": "ETF",
        "Country": "Germany",
        "Currency": "EUR",
        "Isin": f"IE00E2E000{index:02d}",
    }
    for index in range(1, 6)
)


def _business_dates(count: int) -> list[date]:
    values: list[date] = []
    current = date.today()
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current)
        current -= timedelta(days=1)
    return list(reversed(values))


def _quote_rows(code: str) -> list[dict[str, object]]:
    listing_index = int(code.removeprefix("PF"))
    rows: list[dict[str, object]] = []
    for observation, current in enumerate(_business_dates(800)):
        # Distinct trend and cyclical terms keep the five return series
        # non-collinear while remaining deterministic and strictly positive.
        log_price = (
            math.log(70.0 + listing_index * 5)
            + observation * (0.00012 + listing_index * 0.000015)
            + math.sin(observation / (9.0 + listing_index)) * 0.008
            + math.cos(observation / (17.0 + listing_index * 2)) * 0.005
        )
        adjusted_close = round(math.exp(log_price), 6)
        rows.append(
            {
                "date": current.isoformat(),
                "open": adjusted_close,
                "high": round(adjusted_close * 1.002, 6),
                "low": round(adjusted_close * 0.998, 6),
                "close": adjusted_close,
                "adjusted_close": adjusted_close,
                "volume": 100_000 + observation * 10 + listing_index,
            }
        )
    return rows


def _dividend_rows(code: str) -> list[dict[str, object]]:
    listing_index = int(code.removeprefix("PF"))
    today = date.today()
    rows: list[dict[str, object]] = []
    for offset in range(30):
        absolute_month = today.year * 12 + today.month - 1 - offset
        year, month_index = divmod(absolute_month, 12)
        payment_date = date(year, month_index + 1, 15)
        rows.append(
            {
                "date": payment_date.isoformat(),
                "paymentDate": payment_date.isoformat(),
                "period": "Monthly",
                "unadjustedValue": round(0.18 + listing_index * 0.01, 4),
                "currency": "EUR",
            }
        )
    return list(reversed(rows))


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
            self._reply(200, list(_LISTINGS))
            return
        parts = request.path.removeprefix("/api/").split("/", 1)
        if len(parts) == 2 and parts[1].endswith(".XETRA"):
            dataset, symbol = parts
            code = symbol.removesuffix(".XETRA")
            if code in {str(listing["Code"]) for listing in _LISTINGS}:
                if dataset == "eod":
                    self._reply(200, _quote_rows(code))
                    return
                if dataset == "div":
                    self._reply(200, _dividend_rows(code))
                    return
                if dataset == "splits":
                    self._reply(200, [])
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
