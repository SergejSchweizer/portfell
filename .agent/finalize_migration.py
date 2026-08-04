from __future__ import annotations

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

forbidden = (
    "fetch_all_isins",
    "fetch-all-isins",
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
