# PR292 React / Node deletion manifest

Status: reviewed for `refactor/pr292-remove-react-ui`.

This work order removes only the superseded browser implementation under `apps/web/`. The FastAPI API, PostgreSQL catalog, workers, Python research code, Dash presentation package, Compose topology, and Python tests are outside this deletion scope.

## Removed production and build files

- `apps/web/Dockerfile`
- `apps/web/api-contracts.json`
- `apps/web/design-tokens.json`
- `apps/web/index.html`
- `apps/web/package-lock.json`
- `apps/web/package.json`
- `apps/web/playwright.config.ts`
- `apps/web/server.js`
- `apps/web/tsconfig.json`
- `apps/web/tsconfig.node.json`
- `apps/web/vite.config.ts`
- `apps/web/styles/app.css`
- `apps/web/src/app.tsx`
- `apps/web/src/main.tsx`
- `apps/web/src/contracts.ts`
- `apps/web/src/env.ts`
- `apps/web/src/plotly.js-dist-min.d.ts`
- `apps/web/src/vite-env.d.ts`
- `apps/web/src/computation-progress.ts`
- `apps/web/src/quote-progress.ts`
- `apps/web/src/routes.tsx`
- `apps/web/src/api/bivariate-statistics.ts`
- `apps/web/src/api/client.ts`
- `apps/web/src/api/metadata-builder.ts`
- `apps/web/src/api/multivariate-statistics.ts`
- `apps/web/src/api/univariate-statistics.ts`
- `apps/web/src/components/button.tsx`
- `apps/web/src/components/empty-state.tsx`
- `apps/web/src/components/field.tsx`
- `apps/web/src/components/icon-button.tsx`
- `apps/web/src/components/inline-notice.tsx`
- `apps/web/src/components/loading-state.tsx`
- `apps/web/src/components/panel.tsx`
- `apps/web/src/components/progress-stepper.tsx`
- `apps/web/src/components/status-badge.tsx`
- `apps/web/src/hooks/use-debounced-save.ts`
- `apps/web/src/query/client.ts`
- `apps/web/src/query/keys.ts`
- `apps/web/src/query/use-query-resource.ts`
- `apps/web/src/query/use-status-event-stream.ts`
- `apps/web/src/shell/frame.tsx`
- `apps/web/src/shell/metadata-fetch-context.tsx`
- `apps/web/src/shell/project-sidebar.tsx`

## Removed obsolete browser-only tests

- `apps/web/tests/metadata-builder.real-stack.spec.ts`
- `apps/web/tests/setup.ts`
- `apps/web/tests/two-project-workflow.spec.ts`
- `apps/web/tests/unit/client.test.ts`
- `apps/web/tests/unit/components.test.tsx`
- `apps/web/tests/unit/env-routes.test.ts`
- `apps/web/tests/unit/multivariate-statistics.test.ts`
- `apps/web/tests/unit/query.test.ts`
- `apps/web/tests/unit/use-debounced-save.test.tsx`

## Preservation boundary

Equivalent product evidence is owned by the Plotly Dash work orders and the PR275 production cutover. This deletion PR does not edit final Compose topology, FastAPI mount code, numerical algorithms, database migrations, provider credentials, or worker behavior.
