# Quality Checks

## Table Of Contents

- [Purpose](#purpose)
- [Current Shape](#current-shape)
- [Rebase Workflow](#rebase-workflow)
- [Validation Commands](#validation-commands)
- [Conventional Commits](#conventional-commits)
- [Sharding Policy](#sharding-policy)
- [PR Definition Readiness](#pr-definition-readiness)
- [Update Rules](#update-rules)

Last reviewed: 2026-08-30

## Purpose

`GATES.md` is the canonical documentation for Portfell quality checks and local validation commands. Other repository documents should link here instead of repeating the validation contract.

## Current Shape

Portfell uses one local validation contract. Run the applicable focused checks while changing code and the complete check before integration. GitHub runs the complete `merge-gate` once per pull request targeting the integration branch required by the active stack; final integration to `main` still requires the complete gate.

The shard count is intentionally kept at `4` for Unit and Integration tests. Current CI runtime is dominated more by runner setup, checkout, dependency installation, and artifact handling than by individual test execution, so further splitting is not expected to improve wall-clock time yet.

The Plotly Dash replacement series adds a Python Playwright browser acceptance path. During PR355 the legacy npm/Playwright Web tests remain transitional until PR356 deletes the old browser application. The new Dash browser test is Python-only, generates its own deterministic fixture service, makes no external production-network request, and writes the `dash-parity-v1` evidence only after all assertions pass.

Required check families:

- Ruff lint and format.
- Hosted public-repository security gates while legacy hosted code remains.
- Hosted readiness records while the legacy plane remains.
- Pyright strict typing.
- Python Playwright Dash interaction/layout tests on desktop, tablet, and mobile.
- Transitional legacy npm Playwright and real Docker browser tests only until PR356 removes them.
- Pytest Unit and Integration shards.
- Coverage threshold enforcement on `main`.
- Architecture checks.
- Dataset schema validation.
- Conventional Commit validation.

## Rebase Workflow

```text
working branch
        |
        v
rebase onto required integration predecessor
        |
        v
run complete validation
        |
        v
integrated linear main history after gates pass
```

## Validation Commands

Focused and complete validation commands:

```bash
uv run portfell-quality pr
uv run playwright install chromium
uv run pytest -m browser tests/browser -q
```

During the transitional window before PR356, the old Web checks also remain applicable:

```bash
cd apps/web && npm run e2e
bash scripts/run_real_stack_e2e.sh
```

Before integration after rebasing onto the required predecessor, run the complete Python check:

```bash
uv run portfell-quality main
```

The complete check includes Ruff lint and format validation, strict Pyright,
architecture and schema validation, security gates, four Unit and four
Integration pytest-xdist shards, and coverage enforcement:

```text
ruff check .
ruff format --check .
pyright
python -m portfell.architecture_checks
python -m portfell.schema_validation
python -m portfell.security_gates
scripts/pytest_shard.py --suite unit --shard-index N --shard-count 4 -- -q -n auto
scripts/pytest_shard.py --suite integration --shard-index N --shard-count 4 -- -q -n auto
coverage report --fail-under=90
```

The Dash parity gate is intentionally separate from the ordinary pytest shards because it installs and launches a browser. A successful run must produce all 12 populated-page screenshots (four routes across 1440x900, 1024x768, and 390x844) plus machine-readable `dash-parity-v1.json`. The evidence file may say `PASS` only when the real browser journey, layout assertions, console/page error assertions, reference-network negative-space assertion, and screenshot completeness all pass in that same run.

Release cutover can require the stricter public-hosted readiness mode while the old hosted plane exists:

```bash
uv run python -m portfell.hosted_readiness --require-public-hosted
```

Before a hosted cutover rehearsal, require both the approved policy and configured deployment
secrets without printing their values:

```bash
uv run python -m portfell.hosted_readiness --require-public-hosted --require-runtime
```

Apply the idempotent PostgreSQL catalog migrations only through an externally managed,
migration-capable `PORTFELL_DATABASE_URL`; the command never prints that URL:

```bash
uv run python -m portfell.hosted_catalog_migration
```

Verify the migrated catalog is reachable before an import rehearsal:

```bash
uv run python -m portfell.hosted_readiness --require-database
```

Plan a local control-plane import from an operator-provided workspace file without mutating
PostgreSQL. Add `--apply` only after reviewing the dry-run checksum and counts; the applied command
returns count-only normalized project-parity evidence:

```bash
uv run python -m portfell.hosted_import_rehearsal --workspace /secure/local-workspace.json
uv run python -m portfell.hosted_import_rehearsal --workspace /secure/local-workspace.json --apply
```

The deterministic hosted cutover proof composes multi-user auth, credentials, entitlements, scoped analytics, artifact reuse, Web storage safety, local CLI compatibility, and readiness checks while those legacy surfaces are still present:

```bash
uv run python -m portfell.hosted_cutover
```

The local pre-commit hook runs the focused validation contract before accepting commits.

Coverage equivalent:

```text
pytest -n auto --cov=portfell --cov-report=term-missing --cov-fail-under=90
```

## Conventional Commits

Required subject shape:

```text
type(optional-scope): subject
```

Allowed types:

```text
build chore ci docs feat fix perf refactor revert style test
```

The rule applies to every commit subject.

## Sharding Policy

Current setting:

```text
PYTEST_SHARD_COUNT=4
pytest-xdist: pytest -n auto inside every test shard
```

Do not increase shard count by default. Reconsider only when at least one Unit or Integration shard regularly exceeds 5 minutes after setup caching is already healthy.

## PR Definition Readiness

A PR is not definition-ready merely because implementation code exists. Its named focused tests must exist, all required runtime/test dependencies must be locked, and every required acceptance artifact must be generated by an actually executed passing check. Synthetic stack bases and pre-staged descendants never convert a missing predecessor PASS artifact into acceptance evidence.

## Update Rules

Update `GATES.md` whenever any of these change:

- `src/portfell/quality.py`
- local pre-commit gate behavior
- shard count, coverage threshold, or required quality tools
- browser version, interaction manifest, or browser-artifact retention policy
- Dash parity routes, viewports, browser test runner, or `dash-parity-v1` evidence contract
