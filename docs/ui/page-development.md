# UI page development

This document is the required workflow for creating or changing a Portfell React page.

## Canonical locations

- Route registry: `apps/web/src/routes.tsx`
- Page components: `apps/web/src/pages/`
- Shared components: `apps/web/src/components/`
- Shared shell and navigation: `apps/web/src/shell/`
- API client: `apps/web/src/api/client.ts`
- API response contracts: `apps/web/src/contracts.ts`
- Global styles: `apps/web/src/styles.css`
- Page specifications: `docs/ui/windows/`
- Shared layout specifications: `docs/ui/layout/`

## Create a new page

1. Create `apps/web/src/pages/<route-slug>.tsx` and export one page component.
2. Add the component import, a stable `WorkflowPageId`, title, path, and component entry to `apps/web/src/routes.tsx`.
3. Put the entry in its intended workflow order. The navigation is derived from `workflowPages`; do not create a second route or navigation registry.
4. Create `docs/ui/windows/<route-slug>.md` in the same pull request. Define purpose, server-owned inputs, layout regions, states, actions, dependencies, accessibility, responsive behavior, fixtures, tests, security, and out-of-scope behavior.
5. Add or reuse typed API contracts in `apps/web/src/contracts.ts`. Use `requestJson` or `postJson` from `apps/web/src/api/client.ts`; do not call `fetch` directly from a page.
6. Reuse components from `apps/web/src/components/`. Extract a shared component only when at least two pages need the same behavior or the component has an independently testable contract.
7. Add responsive and state-specific styles to `apps/web/src/styles.css`. Preserve visible keyboard focus, associated labels, `aria-live` status messaging, and meaningful disabled states.
8. Extend route and page-contract tests. At minimum, assert the route registration, the primary API action, and the ordering of critical controls.
9. Run the frontend and repository gates listed below.

## Change an existing page

1. Read its specification in `docs/ui/windows/<route-slug>.md` before changing code.
2. Update the page component and specification together. The specification describes the final behavior, not a historical changelog.
3. Keep server-owned business rules on the server. The page may collect inputs, call an endpoint, render progress, and display results; it must not reproduce portfolio, filtering, ingestion, authentication, or authorization logic.
4. When changing API data, update `apps/web/src/contracts.ts`, backend response tests, and page tests in the same pull request.
5. When changing the persistent header, footer, shell, or workflow navigation, update the corresponding file under `docs/ui/layout/` and regression-test every affected page.
6. Remove replaced UI code. Do not leave compatibility renderers, duplicate route registries, hidden legacy controls, or unused page components.

## Required page states

Every asynchronous page operation must define:

- idle state with a clear next action;
- loading or running state with disabled duplicate submission;
- empty state when the server returns no usable data;
- success state with a concise result summary;
- failure state with an actionable message;
- stale-state behavior when upstream selections or metadata change.

Progress indicators must appear before the action that starts or repeats the operation when that ordering is part of the page specification. Actions should remain spatially stable while labels change between idle and running states.

## Validation

Run from the repository root:

```bash
uv lock --check
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run lint-imports
uv run pytest -q
```

Run from `apps/web`:

```bash
npm ci
npm run typecheck
npm run build
node --check server.js
```

Before merging, confirm that generated directories such as `apps/web/node_modules/` and `apps/web/dist/` are not tracked. The pull request must pass the repository `pr-quality` gate.

## Pull-request contract

A UI pull request is complete only when:

- the implementation and matching page specification agree;
- route, API, state, accessibility, and responsive behavior are covered;
- obsolete UI code is removed;
- generated artifacts are absent;
- all required gates pass.
