# <Window Name>

## Identity

- Route: `<route>`
- Funnel stage: `<stage or none>`
- Specification owner: `<feature area>`
- Shared layout: `../layout/header.md`, `../layout/footer.md`

## Purpose

Describe the user goal and the decision or task completed in this window.

## Entry and exit

Define allowed entry routes, prerequisites, deep-link behaviour, successful exits, cancellation, and back-navigation behaviour.

## Server-owned inputs

List authenticated API contracts, opaque ids, project state, immutable snapshots, selections, runs, and artifacts consumed by the window.

## Layout regions

Describe the page header, navigation, context, primary workspace, secondary panels, actions, status areas, and footer use.

## States

Document loading, empty, ready, running, complete, warning, failed, stale, unauthorized, and unavailable states where applicable.

## User actions

For each action define trigger, validation, confirmation, API request, progress, success, failure, retry, and idempotency behaviour.

## Acceptance

- [ ] The window satisfies its stated user goal.
- [ ] All documented states are reproducible with deterministic fixtures.
- [ ] Refresh and deep linking restore server-owned state without duplicate writes.
- [ ] API errors are redacted and actionable.
- [ ] Desktop, tablet, mobile, keyboard, and screen-reader paths are covered.

## Security

The browser performs no financial calculation or authorization decision. The window must not expose provider credentials, tokens, ciphertext, internal paths, database ids, unrestricted artifact ids, raw exceptions, or another user's data.

## Accessibility

Define landmarks, heading order, focus order, accessible names, validation messages, live regions, table alternatives, chart summaries, and reduced-motion behaviour.

## Responsive behaviour

Define desktop, tablet, and mobile layout changes. Mobile must use an intentional layout rather than a scaled desktop page.

## Components

List approved generic components and feature components. Page-specific copies of generic controls are prohibited.

## Tests and fixtures

List component stories, fixture states, browser tests, visual baselines, accessibility checks, and contract tests required by this window.

## Open decisions

Record unresolved product or interaction decisions explicitly. Do not silently invent behaviour in implementation PRs.
