# User Flows

## User roles

| Role | What they can do |
| --- | --- |
| Anonymous visitor | See the login gate only |
| Signed-in researcher | Work through the Research Funnel with project-scoped data |
| Returning researcher | Restore the last selected project and funnel state |
| Local developer | Use the labeled local-dev Google session path for offline UI work |

## Persisted flow

1. Authenticate.
2. Restore the last selected project and snapshot if present.
3. Choose or create a project.
4. Progress through Data, Metadata, Univariate, Filter, Diversification, Portfolio, Validation, Report, Settings, and Account.
5. Review loading, warning, failed, empty, and stale states as explicit states rather than as broken pages.

## First-run onboarding

First-run onboarding must explain, at minimum:

- what the project selector represents
- why the EODHD key is required before project setup
- how the funnel stages depend on prior stages
- that calculations remain server-owned
- that the browser never stores secrets

## State transitions

| Transition | Trigger | Expected visible result |
| --- | --- | --- |
| Anonymous → login | Navigate to `/` without a session | Login gate shown |
| Login → dashboard | Session established | Authenticated shell shown |
| Dashboard → project shell | Project selected or created | Project-specific shell shown |
| Project shell → stats step | Step unlocked and selected | Corresponding state shown |
| Any step → stale | Upstream dependency changes | Downstream state marked stale |
| Any state → loading | Request in flight | Loading indicator shown |
| Any state → failed | Request rejected | Redacted failure text shown |

