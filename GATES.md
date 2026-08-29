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

Last reviewed: 2026-08-29

## Purpose

`GATES.md` is the canonical documentation for Portfell quality checks and local validation commands. Other repository documents should link here instead of repeating the validation contract.

## Current Shape

Portfell uses one local validation contract. Run the applicable focused checks while changing code and the complete check before integration. GitHub runs the complete `merge-gate` once per pull request targeting `main`; it does not repeat the same test families in a separate PR workflow or after the rebase merge.

The shard count is intentionally kept at `4` for Unit and Integration tests. Current CI runtime is dominated more by runner setup, checkout, dependency installation, and artifact handling than by individual test execution, so further splitting is not expected to improve wall-clock time yet.

Required check families:

- Ruff lint and format.
- Hosted public-repository security gates.
- Hosted readiness records for licensing, privacy, retention, backup, restore, and key rotation.
- Pyright strict typing.
- Playwright interaction-inventory tests on desktop.
- Real Docker browser tests for worker-owned metadata refreshes on desktop.
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
rebase onto current main
        |
        v
run complete validation
        |
        v
integrated linear main history
```

## Validation Commands

Focused and complete validation commands:

```bash
uv run portfell-quality pr
cd apps/web && npm run e2e
bash scripts/run_real_stack_e2e.sh
```

Before integration after rebasing onto current `main`, run the complete check:

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

Release cutover can require the stricter public-hosted readiness mode:

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

The deterministic hosted cutover proof composes multi-user auth, credentials, entitlements, scoped analytics, artifact
reuse, Web storage safety, local CLI compatibility, and readiness checks:

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

## Update Rules

Update `GATES.md` whenever any of these change:

- `src/portfell/quality.py`
- local pre-commit gate behavior
- shard count, coverage threshold, or required quality tools
- browser version, interaction manifest, or browser-artifact retention policy
