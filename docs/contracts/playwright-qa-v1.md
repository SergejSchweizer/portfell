# Playwright QA v1

## Contents

- [Coverage](#coverage)
- [Real stack](#real-stack)
- [Evidence](#evidence)

## Coverage

The browser gate covers `/metadata`, `/univariate`, `/bivariate` and
`/multivariate` at 1440x900, 1024x768 and 390x844. It checks console/page
errors, horizontal overflow, persisted reload state, Plotly `customdata`,
checkbox counts, matrices, progress and decisions.

## Real stack

The real-stack test is marked `real_stack` and targets the running Docker /
PostgreSQL/data-share environment via `PORTFELL_REAL_STACK_BASE_URL`. It does
not import or instantiate the deterministic fixture service.

## Evidence

Each journey writes machine-readable assertions and viewport screenshots. The
evidence is sanitized and may not contain credentials, SQL, internal paths or
external reference-site requests.
