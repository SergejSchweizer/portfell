from __future__ import annotations

from pathlib import Path


path = Path("tests/test_hosted_api.py")
text = path.read_text(encoding="utf-8")
old = '''    assert fetched == {
        "country_count": 1,
        "currency_count": 1,
        "exchange_count": 1,
        "instrument_type_count": 1,
        "row_count": 1,
        "status": "succeeded",
    }
'''
new = '''    assert fetched == {
        "exchange_count": 1,
        "requested_exchange_count": 1,
        "row_count": 1,
        "skipped_exchange_count": 0,
        "skipped_exchanges": [],
        "status": "succeeded",
    }
'''
if old not in text:
    raise RuntimeError("generated metadata endpoint expectation not found")
path.write_text(text.replace(old, new), encoding="utf-8")
Path(__file__).unlink()
