# Coverage gate v1

## Contents

- [Threshold](#threshold)
- [Measured scope](#measured-scope)
- [Verification](#verification)

## Threshold

The repository merge gate requires at least **92%** Python line coverage. The
same threshold is used by `portfell-quality` and GitHub's combined shard report.

## Measured scope

Coverage measures `src/portfell`. Five transitional files are explicitly
omitted because PR427 removes them: the monolithic Research service and compute
adapter, the old Univariate refresh entrypoint, and obsolete lock/filter
helpers. This exclusion is temporary and is not a license to add new omissions.

```
active modular code + module contracts + adapters -> measured >= 92%
transitional monolith removal set                    -> omitted until deleted
```

## Verification

Run `uv run pytest -q --cov=portfell --cov-report=term-missing` and confirm the
reported total is at least 92%. The CI workflow combines all unit/integration
shards and applies the same threshold on the exact commit.
