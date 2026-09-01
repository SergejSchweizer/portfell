# Staged-analysis performance v1

## Table of contents

- [Scope](#scope)
- [Final gate](#final-gate)
- [Evidence rules](#evidence-rules)
- [Execution](#execution)

## Scope

This closeout is the final QA contract for the exact staged workflow:
Metadata → full-universe Univariate → read-only filter preview → committed
Selection → Bivariate → default-objective Multivariate (`return_risk`).

## Final gate

The gate must prove monotone Univariate/Bivariate progress, all eight ordered
Multivariate phases, durable restart recovery, exact revision-safe previous/current
labels, and bounded responses (≤100 table rows, ≤500 Univariate chart points,
≤1000 Bivariate chart points, ≤512 KiB callback responses). Browser fixtures run
at 1440×900, 1024×768, and 390×844 with no body overflow or shell flicker.

Warm measurements require at least 30 samples per operation and final budgets of
≤750 ms page content, ≤400 ms filter preview, ≤200 ms status read, and ≤1000 ms
active-compute navigation. The slowest baseline operation must improve by at
least 25% while preserving immutable artifacts and source-snapshot identity.

## Evidence rules

Exactly one sanitized evidence record is produced for a run. It records the
exact 40-hex Git SHA, fixture sizes, latency distributions and p95 values, SQL
query/decoded-row counts, payload maxima, executor policy, progress/restart/race
references, and browser references. Credentials, complete DSNs, and private
market rows are forbidden. Skipped or cancelled jobs are not PASS.

## Execution

```text
uv run pytest -q tests/test_pr396_staged_analysis_closeout.py
uv run portfell-quality pr
uv run portfell-quality merge
```

The test is a deterministic contract check; Docker/browser benchmark evidence
is attached by the merge-gate run and must reference this document.
