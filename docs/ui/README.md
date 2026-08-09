# Portfell UI documentation

Portfell currently has three sequential research modules:

1. [`metadata_builder`](windows/metadata-filter.md) at `/metadata-builder`
2. [`univariate_statistics`](windows/univariate-statistics.md) at `/univariate-statistics`
3. [`bivariate_statistics`](windows/bivariate-statistics.md) at `/bivariate-statistics`

Server-side selection stages may remain for persistence and CLI compatibility, but they are not
browser modules or routes. Bivariate Statistics becomes available when Univariate Statistics completes.

See [Workflow modules](workflow-modules.md) for the module input/output contracts and the
rules for adding later modules. `workflowModules` in `apps/web/src/routes.tsx` owns the
top-level module registry; `workflowPages` owns the concrete routes within those modules.

The canonical implementation registry is `apps/web/src/routes.tsx`. Each registered page must have exactly one matching specification in `docs/ui/windows/`. Shared header and footer behavior belongs in `docs/ui/layout/header.md` and `docs/ui/layout/footer.md`, not in individual page specifications.

Use [UI page development](page-development.md) when creating a page or changing an existing page. A page implementation and its specification must be changed in the same pull request.

The browser owns presentation and interaction state only. Portfolio calculations, metadata filtering, quote ingestion, authentication decisions, and authorization remain server-owned.
