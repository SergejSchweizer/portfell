# Multivariate Statistics

## Purpose

Multivariate Statistics is the fourth research module. It reserves the
project-scoped hand-off from a completed Bivariate Statistics run to
portfolio-level analysis without changing the selected universe or inventing
portfolio results in the browser.

## Server-owned inputs

- the active project;
- its completed Bivariate Statistics run id;
- the Bivariate run's pinned Univariate selection id;
- server-owned workflow status and invalidation state.

## Layout

- Locked state: one `Multivariate Statistics` panel explains that Bivariate
  Statistics must complete first.
- Ready state: one panel confirms the exact Bivariate run and Univariate
  selection supplied to the future multivariate calculation.
- The page contains no compute action until a project-scoped Multivariate API
  contract and persistent run output exist.

## States

- Loading: show the shared loading state.
- Locked: Bivariate Statistics is incomplete, failed, running, or stale.
- Ready: Bivariate Statistics is complete and its immutable run id is shown.
- Failure: workflow-state retrieval failed; show a concise alert.
- Stale: later multivariate work must return to Locked/Ready according to the
  server-owned workflow contract after an upstream change.

## Accessibility and responsive behavior

The page uses the shared semantic panel and a polite status message. It has no
custom chart, pointer, or keyboard interaction. The sidebar remains the only
workflow navigation at every viewport width.

## Security and boundaries

The page reads typed workflow data only. It does not persist calculations,
inspect local storage, render credentials or filesystem paths, infer
authorization, or calculate financial values in React.

## Tests

Route tests assert that the page is the fourth registered route. Workflow-state
tests prove that it remains locked until Bivariate Statistics is complete and
receives the pinned Bivariate run and Univariate selection identifiers.

## Out of scope

Portfolio optimization, risk models, candidate weights, income facts,
multivariate persistence, and any compute endpoint belong to the later
project-scoped Multivariate Statistics implementation.
