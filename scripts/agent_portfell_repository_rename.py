from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
WORKFLOW = ROOT / ".github" / "workflows" / "agent-portfell-repository-rename.yml"

REPLACEMENTS = (
    ("CAMOVAR", "PORTFELL"),
    ("Camovar", "Portfell"),
    ("camovar", "portfell"),
)
SKIP_PARTS = {".git", ".venv", "node_modules", "dist", ".pytest_cache", ".ruff_cache"}


def replace_name(value: str) -> str:
    for old, new in REPLACEMENTS:
        value = value.replace(old, new)
    return value


def project_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and not any(part in SKIP_PARTS for part in path.relative_to(ROOT).parts)
    ]


def replace_text() -> None:
    for path in project_files():
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        updated = replace_name(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")


def rename_paths() -> None:
    candidates = [
        path
        for path in ROOT.rglob("*")
        if ".git" not in path.relative_to(ROOT).parts
        and replace_name(path.name) != path.name
    ]
    for path in sorted(candidates, key=lambda item: len(item.parts), reverse=True):
        if not path.exists():
            continue
        target = path.with_name(replace_name(path.name))
        if target.exists():
            raise RuntimeError(f"rename target already exists: {target}")
        path.rename(target)


def write_ui_documentation() -> None:
    ui_root = ROOT / "docs" / "ui"
    windows_root = ui_root / "windows"
    windows_root.mkdir(parents=True, exist_ok=True)

    for path in windows_root.glob("*.md"):
        path.unlink()

    (ui_root / "README.md").write_text(
        """# Portfell UI documentation

Portfell has four sequential production pages:

1. [`metadata_filter`](windows/metadata-filter.md) at `/metadata-filter`
2. [`univariate_statistics`](windows/univariate-statistics.md) at `/univariate-statistics`
3. [`univariate_filter`](windows/univariate-filter.md) at `/univariate-filter`
4. [`bivariate_statistics`](windows/bivariate-statistics.md) at `/bivariate-statistics`

The canonical implementation registry is `apps/web/src/routes.tsx`. Each registered page must have exactly one matching specification in `docs/ui/windows/`. Shared header and footer behavior belongs in `docs/ui/layout/header.md` and `docs/ui/layout/footer.md`, not in individual page specifications.

Use [UI page development](page-development.md) when creating a page or changing an existing page. A page implementation and its specification must be changed in the same pull request.

The browser owns presentation and interaction state only. Portfolio calculations, metadata filtering, quote ingestion, authentication decisions, and authorization remain server-owned.
""",
        encoding="utf-8",
    )

    (ui_root / "page-development.md").write_text(
        """# UI page development

This document is the required workflow for creating or changing a Portfell React page.

## Canonical locations

- Route registry: `apps/web/src/routes.tsx`
- Page components: `apps/web/src/pages/`
- Shared components: `apps/web/src/components/`
- Shared shell and navigation: `apps/web/src/shell/`
- API client: `apps/web/src/api/client.ts`
- API response contracts: `apps/web/src/contracts.ts`
- Global styles: `apps/web/src/styles.css`
- Page specifications: `docs/ui/windows/`
- Shared layout specifications: `docs/ui/layout/`

## Create a new page

1. Create `apps/web/src/pages/<route-slug>.tsx` and export one page component.
2. Add the component import, a stable `WorkflowPageId`, title, path, and component entry to `apps/web/src/routes.tsx`.
3. Put the entry in its intended workflow order. The navigation is derived from `workflowPages`; do not create a second route or navigation registry.
4. Create `docs/ui/windows/<route-slug>.md` in the same pull request. Define purpose, server-owned inputs, layout regions, states, actions, dependencies, accessibility, responsive behavior, fixtures, tests, security, and out-of-scope behavior.
5. Add or reuse typed API contracts in `apps/web/src/contracts.ts`. Use `requestJson` or `postJson` from `apps/web/src/api/client.ts`; do not call `fetch` directly from a page.
6. Reuse components from `apps/web/src/components/`. Extract a shared component only when at least two pages need the same behavior or the component has an independently testable contract.
7. Add responsive and state-specific styles to `apps/web/src/styles.css`. Preserve visible keyboard focus, associated labels, `aria-live` status messaging, and meaningful disabled states.
8. Extend route and page-contract tests. At minimum, assert the route registration, the primary API action, and the ordering of critical controls.
9. Run the frontend and repository gates listed below.

## Change an existing page

1. Read its specification in `docs/ui/windows/<route-slug>.md` before changing code.
2. Update the page component and specification together. The specification describes the final behavior, not a historical changelog.
3. Keep server-owned business rules on the server. The page may collect inputs, call an endpoint, render progress, and display results; it must not reproduce portfolio, filtering, ingestion, authentication, or authorization logic.
4. When changing API data, update `apps/web/src/contracts.ts`, backend response tests, and page tests in the same pull request.
5. When changing the persistent header, footer, shell, or workflow navigation, update the corresponding file under `docs/ui/layout/` and regression-test every affected page.
6. Remove replaced UI code. Do not leave compatibility renderers, duplicate route registries, hidden legacy controls, or unused page components.

## Required page states

Every asynchronous page operation must define:

- idle state with a clear next action;
- loading or running state with disabled duplicate submission;
- empty state when the server returns no usable data;
- success state with a concise result summary;
- failure state with an actionable message;
- stale-state behavior when upstream selections or metadata change.

Progress indicators must appear before the action that starts or repeats the operation when that ordering is part of the page specification. Actions should remain spatially stable while labels change between idle and running states.

## Validation

Run from the repository root:

```bash
uv lock --check
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run lint-imports
uv run pytest -q
```

Run from `apps/web`:

```bash
npm ci
npm run typecheck
npm run build
node --check server.js
```

Before merging, confirm that generated directories such as `apps/web/node_modules/` and `apps/web/dist/` are not tracked. The pull request must pass the repository `pr-quality` gate.

## Pull-request contract

A UI pull request is complete only when:

- the implementation and matching page specification agree;
- route, API, state, accessibility, and responsive behavior are covered;
- obsolete UI code is removed;
- generated artifacts are absent;
- all required gates pass.
""",
        encoding="utf-8",
    )

    specs = {
        "metadata-filter.md": """# Metadata Filter page

- Route: `/metadata-filter`
- Page ID: `metadata_filter`
- Component: `apps/web/src/pages/metadata-filter.tsx`

## Purpose

Create a server-owned project selection from listing metadata, then fetch historical quotes for that selection.

## Inputs and actions

The page exposes exchange, instrument type, country, currency, and name filters. `Apply metadata filter` creates the selection through the server. After a valid project exists, the page shows quote-fetch progress, status text, and a right-aligned `Fetch quotes` action beneath the progress indicator.

`Fetch quotes` calls `/api/data/load-selected-isins` with the selected `project_id`. Duplicate submission is disabled while the operation is running.

## States

Idle, filtering, selection-ready, quote-running, quote-complete, quote-failed, metadata-empty, and metadata-unavailable states must be explicit. A metadata refresh invalidates and reloads the available filter options.

## Acceptance

The progress indicator precedes the quote action in document order. The action remains disabled until a project selection exists. All fields have visible labels, status changes use `aria-live`, and no filtering or ingestion business logic is implemented in the browser.
""",
        "univariate-statistics.md": """# Univariate Statistics page

- Route: `/univariate-statistics`
- Page ID: `univariate_statistics`
- Component: `apps/web/src/pages/univariate-statistics.tsx`

## Purpose

Run and present server-computed univariate statistics for the active project after quote data is available.

## Contract

The page requests the active project state, starts the univariate-statistics workflow through the API, renders running, empty, success, and failure states, and displays returned statistics without recomputing them in React.

## Acceptance

The primary action is disabled when prerequisites are missing or a run is active. Results use typed contracts, accessible table semantics, stable loading feedback, and a clear upstream-data requirement.
""",
        "univariate-filter.md": """# Univariate Filter page

- Route: `/univariate-filter`
- Page ID: `univariate_filter`
- Component: `apps/web/src/pages/univariate-filter.tsx`

## Purpose

Apply server-owned thresholds to the latest univariate-statistics result and persist the resulting project selection.

## Contract

The page loads available metrics and current values, collects filter thresholds, submits them to the API, and renders the retained and rejected counts returned by the server. It must not implement statistical filtering rules independently in the browser.

## Acceptance

Missing upstream statistics produce a clear empty state. Invalid thresholds are rejected visibly. Submission is idempotent from the user perspective, duplicate running actions are disabled, and stale results are cleared when inputs change.
""",
        "bivariate-statistics.md": """# Bivariate Statistics page

- Route: `/bivariate-statistics`
- Page ID: `bivariate_statistics`
- Component: `apps/web/src/pages/bivariate-statistics.tsx`

## Purpose

Run and present server-computed pairwise statistics for the selection produced by the univariate filter.

## Contract

The page starts the bivariate workflow, reports progress and failures, and renders returned pairwise results using typed API contracts. Pair construction, correlation calculations, storage layout, and ranking remain backend responsibilities.

## Acceptance

The page blocks execution when upstream filtering is incomplete, prevents duplicate runs, represents empty and partial results explicitly, and provides accessible tabular output on desktop and a usable responsive representation on narrow screens.
""",
    }
    for filename, content in specs.items():
        (windows_root / filename).write_text(content, encoding="utf-8")

    architecture = ROOT / "ARCHITECTURE.md"
    if architecture.exists():
        text = architecture.read_text(encoding="utf-8").rstrip()
        section = """

## UI page development

The React route registry is `apps/web/src/routes.tsx`. Every production page has a matching specification under `docs/ui/windows/`. Creating or changing a page must follow `docs/ui/page-development.md`; implementation, route registration, API contracts, tests, and documentation are delivered atomically in one pull request.
"""
        if "## UI page development" not in text:
            architecture.write_text(text + section + "\n", encoding="utf-8")

    agents = ROOT / "AGENTS.md"
    if agents.exists():
        text = agents.read_text(encoding="utf-8").rstrip()
        section = """

## UI changes

Read `docs/ui/page-development.md` before adding or changing a React page. Keep `apps/web/src/routes.tsx`, the page component, its `docs/ui/windows/<route-slug>.md` specification, typed API contracts, and regression tests synchronized in the same pull request. Do not add compatibility renderers or browser-owned financial, ingestion, authentication, or authorization logic.
"""
        if "## UI changes" not in text:
            agents.write_text(text + section + "\n", encoding="utf-8")


def harden_gitignore() -> None:
    path = ROOT / ".gitignore"
    text = path.read_text(encoding="utf-8")
    marker = "!apps/**\n"
    rules = (
        "!apps/**\n"
        "apps/**/node_modules/\n"
        "apps/**/dist/\n"
        "apps/**/.vite/\n"
        "apps/**/coverage/\n"
    )
    if "apps/**/node_modules/" not in text:
        if marker not in text:
            raise RuntimeError("apps allowlist marker not found in .gitignore")
        path.write_text(text.replace(marker, rules, 1), encoding="utf-8")


def remove_temporary_files() -> None:
    SELF.unlink(missing_ok=True)
    WORKFLOW.unlink(missing_ok=True)


def assert_clean_rename() -> None:
    offenders: list[str] = []
    for path in ROOT.rglob("*"):
        if ".git" in path.relative_to(ROOT).parts:
            continue
        relative = path.relative_to(ROOT)
        if "camovar" in str(relative).lower():
            offenders.append(str(relative))
            continue
        if not path.is_file() or any(part in SKIP_PARTS for part in relative.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "camovar" in content.lower():
            offenders.append(str(relative))
    if offenders:
        raise RuntimeError("old repository name remains in: " + ", ".join(sorted(offenders)))


def main() -> None:
    replace_text()
    rename_paths()
    write_ui_documentation()
    harden_gitignore()
    remove_temporary_files()
    assert_clean_rename()


if __name__ == "__main__":
    main()
