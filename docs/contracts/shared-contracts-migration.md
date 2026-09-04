# Shared-contract migration list

## Contents

- [Completed in PR408](#completed-in-pr408)
- [Follow-up migrations](#follow-up-migrations)
- [Rules](#rules)

## Completed in PR408

- Packaging includes `src/portfell_contracts` in the wheel.
- New boundary DTOs import only Python standard-library modules.
- Contract tests exercise serialization, version rejection, safe errors and
  forbidden imports.

## Follow-up migrations

The following application-state types remain adapter-owned and are intentionally
not aliases of the shared package. Each item requires its own compatibility
test before migration:

| Current owner | Future shared type | Migration gate |
| --- | --- | --- |
| `portfell.app_state.contracts.AnalysisJobRecord` | `JobProgress` plus workflow command | PR411 |
| `portfell.app_state.contracts.AnalysisArtifactRecord` | `ArtifactManifest` | PR410 |
| `portfell.app_state.contracts.MetadataUniverseRecord` | `MetadataUniverseId` hand-off | PR409/412 |
| `portfell.app_state.contracts.UnivariateSelectionRecord` | `UnivariateSelectionId` hand-off | PR409/414 |

## Rules

No caller may create a second local alias for a shared ID or DTO. A migration
must change imports explicitly, preserve wire names, and retain a round-trip
test. Business calculations and database adapters stay outside this package.
