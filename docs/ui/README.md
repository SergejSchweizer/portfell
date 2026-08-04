# Portfell UI documentation

Portfell has four sequential production pages:

1. [`metadata_filter`](windows/metadata-filter.md) at `/metadata-filter`
2. [`univariate_statistics`](windows/univariate-statistics.md) at `/univariate-statistics`
3. [`univariate_filter`](windows/univariate-filter.md) at `/univariate-filter`
4. [`bivariate_statistics`](windows/bivariate-statistics.md) at `/bivariate-statistics`

The canonical implementation registry is `apps/web/src/routes.tsx`. Each registered page must have exactly one matching specification in `docs/ui/windows/`. Shared header and footer behavior belongs in `docs/ui/layout/header.md` and `docs/ui/layout/footer.md`, not in individual page specifications.

Use [UI page development](page-development.md) when creating a page or changing an existing page. A page implementation and its specification must be changed in the same pull request.

The browser owns presentation and interaction state only. Portfolio calculations, metadata filtering, quote ingestion, authentication decisions, and authorization remain server-owned.
