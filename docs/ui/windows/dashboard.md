# Dashboard Window

## Identity

- Route: `/dashboard`
- Funnel stage: none
- Shared layout: authenticated header and footer

## Purpose

Orient new and returning users, summarize data and portfolio status, surface warnings, and provide the shortest safe path into the current research workflow.

## Server-owned inputs

Authenticated user summary, recent projects, current project pointer, credential status, visible snapshot coverage, latest analysis and monitoring status, warnings, and account readiness.

## Layout and states

Provide first-run onboarding, recent projects, continue-research action, data-status summary, portfolio-monitoring summary, warnings, and account navigation. Cover empty, onboarding, ready, partially configured, stale, failed, and loading states.

## User actions

Continue an existing project, create a project, enter credential settings, start or resume onboarding, open warnings, and navigate to account controls.

## Acceptance

- [ ] A new user sees an accurate empty state and no pre-existing market data.
- [ ] A returning user sees only their projects, snapshots, runs, and warnings.
- [ ] Continue Research opens the exact persisted funnel stage without creating new records.
- [ ] Stale downstream results are visibly distinguished from current results.
- [ ] Desktop, tablet, mobile, keyboard, and screen-reader flows are covered.

## Security

All summaries resolve through the authenticated session and user-owned records. Guessed ids, browser cache, prefetching, or stale client state cannot reveal another user's activity.

## Components and tests

Use approved PageHeader, OnboardingCard, ProjectTable, StatusCard, WarningList, EmptyState, and PrimaryAction components. Fixtures cover new, returning, stale, warning, and failure scenarios.
