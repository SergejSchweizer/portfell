# Staged-analysis performance baseline v1

## Table of contents

- [Purpose](#purpose)
- [Deterministic fixture](#deterministic-fixture)
- [Measurements](#measurements)
- [Reproduction](#reproduction)

## Purpose

This QA record freezes the correctness and read-plane baseline for the staged
Metadata → Univariate → Selection → Bivariate → Multivariate workflow. It is
sanitized: it contains no credentials, DSNs, or market rows.

## Deterministic fixture

The fixture contract uses 5,000 full-identity metadata listings, a 400-member
selection, at least 100,000 persisted Bivariate pair rows, and paginated
Multivariate decision/structure artifacts. A controllable job advances progress
without market I/O or wall-clock sleeps. Every row is ordered by the complete
identity `(isin, exchange, code)` and every analytical read is bounded.

## Measurements

The baseline gate records page-content, filter-preview, status-read, and
active-compute navigation latency distributions (minimum 30 warm samples), SQL query
counts, decoded rows, callback payload bytes, and executor capacity. The
initial budgets are page content ≤1,500 ms, filter preview ≤800 ms, status read
≤400 ms, and active-compute navigation ≤2,000 ms. These values are evidence
targets, not claims about a live market environment.

## Reproduction

Run the deterministic contract and the normal merge gate from the repository
root:

```text
uv run pytest -q tests/test_pr394_staged_analysis_baseline.py
uv run portfell-quality pr
```

The test verifies the frozen workflow contract, bounded page/chart caps,
revision labels, and the absence of an unbounded analytical read in normal page
contracts. A future Docker benchmark may append a timestamped measurement block;
it must retain this immutable fixture definition.
