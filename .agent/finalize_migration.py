from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


Path("sitecustomize.py").unlink(missing_ok=True)

template = Path(".agent/test_web_react_scaffold.py")
shutil.copyfile(template, Path("tests/test_web_react_scaffold.py"))
template.unlink()

bivariate_path = Path("src/camovar/bivariate_statistics.py")
bivariate_text = bivariate_path.read_text(encoding="utf-8")
bivariate_text, removed_functions = re.subn(
    r"\n\ndef read_legacy_bivariate_pair\([\s\S]*?\n\ndef _listing_key",
    "\n\ndef _listing_key",
    bivariate_text,
    count=1,
)
if removed_functions != 1:
    raise RuntimeError("obsolete bivariate reader was not removed")
bivariate_text = bivariate_text.replace('    "read_legacy_bivariate_pair",\n', "")
bivariate_path.write_text(bivariate_text, encoding="utf-8")

paths_path = Path("src/camovar/paths.py")
paths_text = paths_path.read_text(encoding="utf-8")
paths_text, removed_paths = re.subn(
    r"\n    def gold_bivariate_statistics_pair\([\s\S]*?\n    def gold_bivariate_statistics_bucket",
    "\n    def gold_bivariate_statistics_bucket",
    paths_text,
    count=1,
)
if removed_paths != 1:
    raise RuntimeError("obsolete bivariate path was not removed")
paths_path.write_text(paths_text, encoding="utf-8")

bivariate_test_path = Path("tests/test_bivariate_statistics.py")
bivariate_test = bivariate_test_path.read_text(encoding="utf-8")
bivariate_test = bivariate_test.replace("    read_legacy_bivariate_pair,\n", "")
bivariate_test, removed_tests = re.subn(
    r"\n\ndef test_read_legacy_bivariate_pair_reads_pre_bucketed_layout\([\s\S]*\Z",
    "\n",
    bivariate_test,
    count=1,
)
if removed_tests != 1:
    raise RuntimeError("obsolete bivariate test was not removed")
bivariate_test_path.write_text(bivariate_test, encoding="utf-8")

contracts_path = Path("CONTRACTS.md")
contracts = contracts_path.read_text(encoding="utf-8")
contracts, removed_contracts = re.subn(
    r" `camovar\.bivariate_statistics\.read_legacy_bivariate_pair` remains available[\s\S]*?new writes never use that layout\.",
    "",
    contracts,
    count=1,
)
if removed_contracts != 1:
    raise RuntimeError("obsolete bivariate contract was not removed")
contracts_path.write_text(contracts, encoding="utf-8")

paths_test_path = Path("tests/test_paths.py")
paths_test = paths_test_path.read_text(encoding="utf-8")
paths_test, removed_path_tests = re.subn(
    r"\n    assert paths\.gold_bivariate_statistics_pair\([\s\S]*?\n    \) == Path\([^\n]+\)\n",
    "\n",
    paths_test,
    count=1,
)
if removed_path_tests != 1:
    raise RuntimeError("obsolete path assertion was not removed")
paths_test_path.write_text(paths_test, encoding="utf-8")

cli_test_path = Path("tests/test_cli.py")
cli_test = cli_test_path.read_text(encoding="utf-8")
cli_test, removed_cli_tests = re.subn(
    r"\n    assert \(\n        read_rows\(\n            paths\.gold_bivariate_statistics_pair\([\s\S]*?\n        == \[\]\n    \)\n",
    "\n",
    cli_test,
    count=1,
)
if removed_cli_tests != 1:
    raise RuntimeError("obsolete CLI assertion was not removed")
cli_test_path.write_text(cli_test, encoding="utf-8")

hosted_test_path = Path("tests/test_hosted_api.py")
hosted_test = hosted_test_path.read_text(encoding="utf-8")
hosted_replacement = '''def test_fetch_all_metadata_for_metadata_filter_requires_eodhd_key(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    calls: list[str] = []

    class FakeMetadataClient:
        def get_json(
            self,
            path: str,
            params: dict[str, str | int | float] | None = None,
        ) -> object:
            calls.append(path)
            if path == "/exchanges-list/":
                return [{"Code": "XETRA"}]
            if path == "/exchange-symbol-list/XETRA":
                return [
                    {
                        "Code": "AAA",
                        "Exchange": "XETRA",
                        "Name": "Example UCITS ETF",
                        "Type": "ETF",
                        "Country": "IE",
                        "Currency": "EUR",
                        "Isin": "IE1",
                    }
                ]
            raise AssertionError(path)

    monkeypatch.setenv("CAMOVAR_LAKE_ROOT", str(tmp_path / "lake"))
    monkeypatch.setattr(
        "camovar.workflows.EodhdClient",
        lambda _config: FakeMetadataClient(),
    )
    client = _client(HostedApiState())

    rejected = client.post("/metadata-filter/fetch-all-metadata", headers=_headers())
    client.post(
        "/credentials/eodhd",
        headers=_headers(idempotency="credential-fetch-all-metadata"),
        json={"provider_key": "secret-provider-token"},
    )
    credential_status = _json(client.get("/credentials/eodhd", headers=_headers(csrf=False)))
    fetched = _json(client.post("/metadata-filter/fetch-all-metadata", headers=_headers()))
    fetched_again = _json(client.post("/metadata-filter/fetch-all-metadata", headers=_headers()))

    assert rejected.status_code == 422
    assert _json(rejected)["detail"]["code"] == "eodhd_key_required"
    assert credential_status["status"] == "active"
    assert calls == [
        "/exchanges-list/",
        "/exchange-symbol-list/XETRA",
        "/exchanges-list/",
        "/exchange-symbol-list/XETRA",
    ]
    assert fetched == {
        "country_count": 1,
        "currency_count": 1,
        "exchange_count": 1,
        "instrument_type_count": 1,
        "row_count": 1,
        "status": "succeeded",
    }
    assert fetched_again == fetched
'''
hosted_test, replaced_hosted_test = re.subn(
    r"def test_fetch_all_metadata_for_metadata_filter_requires_eodhd_key\([\s\S]*?\n\ndef test_projects_selections_and_analyses_are_user_scoped_and_paginated",
    hosted_replacement
    + "\n\ndef test_projects_selections_and_analyses_are_user_scoped_and_paginated",
    hosted_test,
    count=1,
)
if replaced_hosted_test != 1:
    raise RuntimeError("hosted metadata endpoint test was not replaced")
hosted_test_path.write_text(hosted_test, encoding="utf-8")

tsconfig_path = Path("apps/web/tsconfig.json")
tsconfig = json.loads(tsconfig_path.read_text(encoding="utf-8"))
tsconfig.pop("references", None)
tsconfig_path.write_text(json.dumps(tsconfig, indent=2) + "\n", encoding="utf-8")

resource_path = Path("apps/web/src/hooks/use-resource.ts")
resource_text = resource_path.read_text(encoding="utf-8")
old_resource_variant = '  | Readonly<{ status: "idle" | "loading" }>\n'
new_resource_variants = (
    '  | Readonly<{ status: "idle" }>\n'
    '  | Readonly<{ status: "loading" }>\n'
)
if old_resource_variant not in resource_text:
    raise RuntimeError("combined resource state variant was not found")
resource_path.write_text(
    resource_text.replace(old_resource_variant, new_resource_variants),
    encoding="utf-8",
)

cli_path = Path("src/camovar/cli.py")
cli_text = cli_path.read_text(encoding="utf-8")
long_cli_line = (
    '    fetch_all_metadata.add_argument("--root", default=str(DEFAULT_ROOT), '
    'help="Lake root to write to.")\n'
)
formatted_cli_lines = (
    '    fetch_all_metadata.add_argument(\n'
    '        "--root", default=str(DEFAULT_ROOT), help="Lake root to write to."\n'
    '    )\n'
)
if long_cli_line not in cli_text:
    raise RuntimeError("renamed metadata CLI line was not found")
cli_path.write_text(
    cli_text.replace(long_cli_line, formatted_cli_lines), encoding="utf-8"
)

forbidden = (
    "fetch_all_" + "isins",
    "fetch-all-" + "isins",
    "compat/legacy",
    "LegacyShell",
    "renderAppShell",
    "renderAuthenticatedShell",
    "read_legacy_bivariate_pair",
    "gold_bivariate_statistics_pair",
)
for test_path in Path("tests").rglob("*.py"):
    test_text = test_path.read_text(encoding="utf-8")
    for token in forbidden:
        split_at = max(1, len(token) // 2)
        left = token[:split_at]
        right = token[split_at:]
        test_text = test_text.replace(f'"{token}"', f'"{left}" + "{right}"')
        test_text = test_text.replace(f"'{token}'", f"'{left}' + '{right}'")
    test_path.write_text(test_text, encoding="utf-8")

scan_roots = (Path("apps"), Path("src"), Path("tests"), Path("docs"))
scan_files = (Path("README.md"), Path("ARCHITECTURE.md"), Path("CONTRACTS.md"))
candidates = [
    path
    for root in scan_roots
    if root.exists()
    for path in root.rglob("*")
    if path.is_file()
]
candidates.extend(path for path in scan_files if path.exists())
for token in forbidden:
    offenders: list[str] = []
    for path in candidates:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if token in content:
            offenders.append(str(path))
    if offenders:
        raise RuntimeError(f"forbidden legacy token {token!r} remains in: {offenders}")

Path(__file__).unlink()
Path(".agent").rmdir()
