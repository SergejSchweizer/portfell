# Fixture Scenarios

## Version

`camovar-ui-fixtures-v1`

## Purpose

Fixture scenarios provide deterministic UI states for local-development and test-only
browser coverage. They are used to open pages and major component states without live
Google, EODHD, PostgreSQL, or FastAPI dependencies.

## Scenario catalogue

| Scenario | Primary use |
| --- | --- |
| `empty-user` | Anonymous or empty shell coverage |
| `missing-credential` | Shell with no saved EODHD credential |
| `invalid-credential` | Saved credential rejected by provider boundary |
| `free-key` | Free synthetic key shell coverage |
| `paid-key` | Paid synthetic key shell coverage |
| `empty-project` | Empty project-state coverage |
| `partial-data` | Partially loaded data and partial progress |
| `statistics-running` | Running-state statistics workflow |
| `statistics-complete` | Completed statistics workflow |
| `stale-analysis` | Upstream-changed stale downstream state |
| `provider-error` | Redacted provider error coverage |
| `authorization-error` | Authorization error coverage |
| `portfolio-comparison` | Comparison and portfolio preview states |
| `stress-warning` | Warning-state coverage for stress views |
| `recommendation-ready` | Recommendation/report-ready shell states |
| `slow-api` | Slow-response and loading-state coverage |
| `offline-recovery` | Offline recovery and reconnect coverage |

## Fixture rules

- Fixture selection is only available when the UI is explicitly running in test or local-dev mode.
- Fixture names are versioned and deterministic.
- Fixture data must remain synthetic, redacted, and free of production identifiers.
- Fixture replay must not create persisted server records.
- Browser controls for fixture selection are read-only in production mode.

