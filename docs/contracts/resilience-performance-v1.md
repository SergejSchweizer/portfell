# Resilience and performance v1

## Contents

- [Recovery](#recovery)
- [Idempotency](#idempotency)
- [Isolation budget](#isolation-budget)
- [Evidence](#evidence)

## Recovery

Workers persist a lease before computation. If a worker dies, the workflow
repository returns the expired command to `queued`; a `.part` artifact remains
invisible and is cleaned during the next publication attempt.

## Idempotency

The command idempotency key and immutable artifact ID are unique. Concurrent
duplicate requests may observe the same published manifest but cannot create a
second result or overwrite different bytes.

## Isolation budget

Under the bounded fixture workload, Metadata/Univariate persisted reads have a
documented p95 budget of 2 seconds while Bivariate/Multivariate workers are
CPU-saturated. Gateway health remains below the same budget with one module
stopped.

## Evidence

Resilience evidence records command IDs, artifact IDs, elapsed percentiles and
failure codes only. Credentials, SQL, filesystem paths and raw financial rows
are excluded.
