# Quality Gates

Last reviewed: 2026-08-20.

`GATES.md` is the canonical quality-gate authority. No backlog item may weaken these requirements.

## Pull-request gate

`pr-quality` runs on every pull request and non-main branch push. Lint, strict typing, four Unit shards, four Integration shards, and the production Python/Dash image/Compose validation run in parallel. The stable required aggregate check is `pr-quality`.

The lint gate runs Ruff lint/format, hosted security gates, Conventional Commit validation for branch commits, and PR-title/squash-subject validation. Branches and commits for the active backlog series use the PR-key-bearing scope, for example `feat/pr270-multivariate-pareto-selector` and `feat(pr270-multivariate-pareto-selector): add eligibility and pareto selection`.

## Main merge gate

`merge-gate` runs on the exact `main` SHA after merge. Lint/architecture/schema/security, strict Pyright, four Unit shards, four Integration shards, and the production app image/Compose validation run in parallel. Coverage artifacts from all eight pytest shards are combined and must satisfy **95%** line coverage.

## Production UI evidence

React/TypeScript/Vite/Node are no longer production dependencies. The only browser UI is Plotly Dash mounted into FastAPI. The final long-running Compose services are exactly `postgres`, `app`, and `project-bootstrap-worker`.

## Merge policy

- `pr-quality` must pass before merge.
- Same-repository non-draft PRs may use the existing squash auto-merge workflow after `pr-quality` succeeds.
- PR title becomes the squash subject and must satisfy Conventional Commits.
- `merge-gate` validates the exact landed `main` SHA.
- Unit/Integration shard count is fixed at four unless measured CI runtime justifies a change.
- Coverage threshold is 95% and may only be changed in an explicit quality-policy PR.

## Local equivalents

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run portfell-quality pr
docker build --file apps/api/Dockerfile --tag portfell-app:local .
docker compose config --quiet
```

For post-merge coverage equivalence:

```bash
uv run pytest -n auto --cov=portfell --cov-report=term-missing --cov-fail-under=95
```
