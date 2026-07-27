# Loading And Error Semantics

## Required states

The spec vocabulary is: loading, empty, warning, failed, and stale states.

Every page specification must describe these states where applicable:

- idle
- loading
- ready
- empty
- warning
- failed
- stale
- complete
- cancelled

## Rules

- Loading states explain what is being fetched or computed.
- Empty states explain why content is missing and what action can fill it.
- Warning states preserve partial results when safe.
- Failed states redact provider or internal details.
- Stale states explain which dependency changed.
- Complete states confirm the server-owned result arrived.

## Copy requirements

- User-visible errors must be actionable and redacted.
- Debug detail must stay out of screenshot fixtures.
- Retry affordances should be explicit when a retry is meaningful.
