# Portfell quality gates

`GATES.md` is the quality/coverage authority for the final Python-only Portfell runtime.

## Local PR gate

Run before every implementation PR update:

```bash
uv run portfell-quality pr
```

This executes, in order:

- Ruff lint;
- Ruff format check;
- repository security gates;
- strict Pyright;
- the pytest suite in parallel;
- Conventional Commit validation for the branch commit range.

A non-zero result is a failed PR gate. Do not bypass it.

## Local merge gate

Run before a branch is considered merge-ready:

```bash
uv run portfell-quality merge
```

`main` is retained as an alias for the same complete command set, but new documentation and automation should use `merge`.

The merge layer executes:

- Ruff lint and formatting;
- architecture boundary validation;
- dataset schema validation;
- security validation;
- strict Pyright;
- parallel pytest with `--cov=portfell` and `--cov-fail-under=90`;
- isolated Docker PostgreSQL market-source contract QA;
- clean working-tree checks;
- Conventional Commit validation.

The Python coverage threshold is **90% minimum**. A result below 90% fails the merge gate.

## GitHub `merge-gate`

Every pull request targeting the merge line must obtain a successful GitHub workflow named `merge-gate`. It is the repository merge authority and must not be replaced by a second overlapping workflow.

The final workflow runs these independent families:

1. `merge-lint-quality` — Ruff, architecture, dataset-schema, security, branch-subject and clean-tree checks.
2. `merge-type-quality` — strict Pyright.
3. `merge-dash-browser` — Python Playwright Chromium acceptance for the four Plotly Dash pages; uploads `dash-parity-v1` evidence.
4. `merge-unit-tests-1..4` — four deterministic unit-test shards with coverage data.
5. `merge-integration-tests-1..4` — four deterministic integration-test shards with coverage data.
6. final `merge-gate` aggregation — requires all preceding families to succeed, combines coverage shards, and enforces 90% coverage.

All third-party GitHub Actions are pinned to full commit SHAs. Workflow permissions are top-level read-only unless a narrowly scoped workflow explicitly requires more.

## Dash browser acceptance

The browser gate is Python Playwright only. No Node/Vite/Vitest/React browser gate exists in the final runtime.

Required browser evidence covers:

- one Metadata → Univariate → Bivariate → Multivariate journey;
- persistence after page reload;
- typed/redacted failure followed by retry;
- upstream revision invalidation of downstream readiness;
- exactly four navigation items/routes;
- zero Portfell page errors and console errors;
- zero runtime requests to `financial-dashboard-example.plotly.app`;
- no page-level horizontal overflow;
- screenshots for all four routes at `1440x900`, `1024x768`, and `390x844` (12 screenshots total).

The `dash-parity-v1` PASS artifact is valid only when produced by an actually executed successful browser job for the exact commit. A manually created JSON file or a workflow that failed before runner assignment is not PASS evidence.

## Market-source contract gate

The merge layer runs:

```bash
bash scripts/run_market_source_contract_qa.sh
```

The isolated PostgreSQL fixture validates the external-market contract without requiring the live production host. The contract must keep market access read-only, preserve full listing identity, enforce coherent snapshot semantics, and reject forbidden writes/sync authority.

Live xetra-loader acceptance remains a separate explicitly enabled environment check and never leaks credentials or complete credential-bearing DSNs into evidence.

## SQL and runtime boundaries

Quality checks must keep these boundaries true:

- Dash modules execute no SQL;
- xetra-loader SQL exists only under `src/portfell/market_source/**`;
- Portfell application-state SQL exists only under `src/portfell/app_state/**`;
- no provider/EODHD acquisition runtime exists;
- no first-party React/Vite/TypeScript/TanStack/Node Web runtime exists;
- no retired hosted Portfell database repository/control plane exists;
- root `config.yaml` is gitignored and excluded from images/artifacts;
- tracked `config.example.yaml` is secret-free.

## Commit and branch contract

Non-main branches use the typed branch format frozen by `AGENTS.md`/`BACKLOG.md`. Every branch commit uses Conventional Commits and the owning branch slug as scope. Example:

```text
test(pr359-dash-clean-runtime-qa): enforce clean runtime negative space
```

Do not merge a branch whose required predecessor acceptance is missing. Synthetic stack bases may be used for pre-staging only; they do not substitute for the real predecessor PASS/merge evidence.

## Merge policy

Repository automation is rebase-oriented. A pull request may complete only after the successful `merge-gate`; failed/skipped/zero-step workflow runs are never treated as success.

The destructive production cutover in PR360 has additional evidence requirements in `docs/runbooks/dash-production-cutover.md`. Those operational checks are not replaced by ordinary unit-test success.