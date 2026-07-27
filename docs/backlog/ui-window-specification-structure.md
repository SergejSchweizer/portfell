# UI Window Specification Structure

Last reviewed: 2026-07-27

## Backlog integration

This requirement applies to PR111 and every later Camovar Web UI PR. It refines the page-specification scope defined by the component-driven React UI refactor stack.

PR111 must establish and validate the canonical `docs/ui/` specification tree. PR112 through PR119 and product-facing PR102 through PR108 must keep these files synchronized with implemented routes and shared layout behaviour.

## Canonical structure

```text
docs/ui/
├── README.md
├── layout/
│   ├── header.md
│   └── footer.md
├── templates/
│   └── window-spec-template.md
└── windows/
    ├── login.md
    ├── dashboard.md
    ├── projects.md
    ├── data.md
    ├── metadata.md
    ├── univariate.md
    ├── filter.md
    ├── diversification.md
    ├── portfolio.md
    ├── validation.md
    ├── report.md
    ├── settings.md
    └── account.md
```

## Rules

1. Every route-level production UI window has exactly one canonical Markdown file under `docs/ui/windows/`.
2. Global header behaviour is specified only in `docs/ui/layout/header.md`.
3. Global footer behaviour is specified only in `docs/ui/layout/footer.md`.
4. Window files reference shared layout contracts instead of copying header or footer requirements.
5. Every new route adds its specification and registry entry in the same PR.
6. A window specification contains identity, purpose, entry and exit rules, server-owned inputs, layout regions, states, actions, acceptance, security, accessibility, responsive behaviour, components, tests, fixtures, and open decisions.
7. Codex implementation prompts should name the exact window specification and shared layout specifications that define the requested change.
8. Browser components perform no financial calculations or authorization decisions.

## Acceptance for PR111

- [ ] `docs/ui/README.md` is the canonical registry of all production windows.
- [ ] Header and footer each have their own Markdown contract under `docs/ui/layout/`.
- [ ] Every currently registered and planned route-level window has a non-empty Markdown specification under `docs/ui/windows/`.
- [ ] Every window file follows the mandatory section structure or documents an approved exception.
- [ ] Documentation validation fails when a route has no registered specification, a registry path does not exist, two files claim the same canonical route, or a window copies shared header or footer requirements instead of referencing them.
- [ ] Documentation validation fails when browser responsibilities include financial calculation, credential persistence, authorization decisions, unrestricted artifact access, or server-secret handling.
- [ ] Header and footer contracts cover unauthenticated, authenticated, project-context, narrow-viewport, keyboard, and screen-reader variants where applicable.
- [ ] The documentation tree can be validated without Google, EODHD, PostgreSQL, live FastAPI, or production secrets.

## Acceptance for later UI PRs

- [ ] Any changed window updates its own specification in the same PR when behaviour, API contracts, states, actions, layout, accessibility, or responsive rules change.
- [ ] Shared header or footer changes update the corresponding layout specification and all affected tests.
- [ ] Component stories, deterministic fixtures, Playwright flows, and visual baselines map back to the relevant window specification.
- [ ] Pull-request validation reports the affected window specifications for every production route or shared-layout change.
- [ ] No product-facing PR extends the legacy renderer as an alternative to the React component and specification foundation.

## Determinism and idempotency

Registry ordering, canonical route names, paths, section names, and validation rules are versioned. Re-running documentation validation against unchanged files produces the same result and does not change source or runtime state.
