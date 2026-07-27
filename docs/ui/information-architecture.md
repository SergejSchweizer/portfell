# Information Architecture

## Top-level research funnel

The current and planned Research Funnel is organized as:

1. Data
2. Metadata
3. Univariate
4. Filter
5. Diversification
6. Portfolio
7. Validation
8. Report
9. Settings
10. Account

The current shell also includes baseline project selection and statistics states that support the funnel.

## Route map

| Route area | User intent | Shell location |
| --- | --- | --- |
| Login | Authenticate and establish a session | Public gate before the authenticated shell |
| Dashboard | Enter the authenticated workspace | Authenticated shell top level |
| Data | Load or inspect current listing data | Research Funnel route body |
| Metadata | Filter and create projects | Research Funnel route body |
| Univariate | Inspect per-listing metrics | Research Funnel route body |
| Filter | Apply reusable metric predicates | Research Funnel route body |
| Diversification | Inspect pairwise and clustering signals | Research Funnel route body |
| Portfolio | Build and review portfolio outputs | Research Funnel route body |
| Validation | Check risk, quality, and readiness | Research Funnel route body |
| Report | Review narrative and export surfaces | Research Funnel route body |
| Settings | Adjust user-scoped preferences | Research Funnel route body |
| Account | Session and identity management | Authenticated shell and route body |

## Persisted UI state

The UI may persist only user-facing, non-secret state such as:

- selected project
- selected snapshot
- selected funnel step
- accepted display preferences
- in-flight run identifiers returned by the server

It must not persist:

- session cookies
- OAuth tokens
- provider secrets
- internal filesystem paths
- raw provider payloads

