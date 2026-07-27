# Global Header

## Purpose

Provide stable product identity, authenticated-user identity, project context, navigation access, and globally relevant actions without duplicating page-specific controls.

## Variants

- Unauthenticated: Camovar identity and login-related context only.
- Authenticated without project: product identity, user identity, account navigation, and project selection or creation entry.
- Authenticated with project: product identity, user identity, active project, current snapshot status, funnel navigation access, and account navigation.
- Narrow viewport: compact product identity and an accessible navigation trigger; no hidden critical status.

## Required content

- Camovar Research brand.
- Authenticated Google display name or email in lowercase; local development sessions visibly labelled.
- Active project name where available.
- Current snapshot or stale-state indicator where available.
- Navigation trigger or persistent navigation according to viewport.
- Logout/account entry without exposing tokens or session details.

## Behaviour

The header is persistent across authenticated route changes. It reads server-owned session and project context and must not create projects, snapshots, selections, or runs on render, refresh, or navigation.

## Acceptance

- [ ] Header variants render correctly for unauthenticated, new-user, returning-user, active-project, stale-project, and local-development sessions.
- [ ] Long user and project names do not overlap controls.
- [ ] Project and snapshot context remains consistent after route changes and refresh.
- [ ] Mobile navigation is keyboard and screen-reader accessible.
- [ ] No page reimplements the global header.

## Security

The header must never render provider credentials, Google tokens, session tokens, ciphertext, database ids, internal storage paths, raw exception payloads, or project context belonging to another user.

## Accessibility

Use a semantic banner landmark, labelled navigation, visible focus, logical tab order, accessible menu state, and screen-reader announcements when project or snapshot status materially changes.

## Responsive behaviour

Desktop may show full product, project, snapshot, and navigation context. Tablet may condense secondary labels. Mobile uses a compact header and navigation drawer while preserving identity, active-project context, warnings, and logout access.
