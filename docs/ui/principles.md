# UI Principles

## Version

`camovar-ui-spec-v1`

## Principles

1. The browser is a presentation and orchestration layer only.
2. financial calculations remain server-owned.
3. authorization decisions remain server-owned.
4. Browser components may render state, not infer hidden business rules.
5. Every user-visible state must be documentable, deterministic, and fixtureable.
6. Synthetic fixtures must never expose secrets, cookies, provider responses, or cross-user data.
7. Page specs should describe what the user can see and do, not implementation accidents.
8. Shared UI should be reusable through typed component contracts, not copied page markup.
9. Responsive rules must preserve task completion, not merely geometry.
10. Loading, empty, warning, failed, and stale states are first-class states.

## Boundary model

| Layer | Responsibility | Must not do |
| --- | --- | --- |
| generic components | Reusable UI primitives and layout atoms | Hard-code business decisions or route-specific logic |
| feature components | Encapsulate one Research Funnel task or subtask | Compute portfolio math or change authorization |
| Pages | Compose route-level layout and state ownership | Reimplement shared controls |
| API clients | Typed request/response boundary | Render layout or mutate local business state silently |
| Server-owned logic | Authentication, authorization, persistence, calculations | Depend on browser-held secrets or untrusted client claims |

## Versioning rules

- Route names, page IDs, and component IDs are committed.
- State names are lowercase and hyphenated where practical.
- The same visible state must map to the same page-spec identifier across revisions.
