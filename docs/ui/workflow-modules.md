# Workflow modules

Portfell's active research workflow is divided into four modules. A module owns
its browser routes, typed API facade, persisted output identifiers, result state,
and UI specification. Modules communicate only through server-persisted IDs and
shared workspace contracts; one module must not read another module's local UI
state.

| Module | Browser entry points | Input contract | Output contract | Boundary |
| --- | --- | --- | --- | --- |
| Metadata Builder | `/metadata-builder` | EODHD credential and metadata criteria | Project and metadata selection ID | Builds the project-scoped instrument universe; it does not calculate statistics. |
| Univariate Statistics | `/univariate-statistics` | Metadata selection and quote-run IDs | Per-ISIN statistics, selection settings, and the automatic selected-ISIN set | Calculates single-instrument statistics; it does not build metadata or pairwise matrices. |
| Bivariate Statistics | `/bivariate-statistics` | Univariate Statistics selection ID | Pairwise results, covariance matrix, and correlation matrices | Calculates pairwise relationships; it does not alter the upstream selection or construct a portfolio. |
| Multivariate Statistics | `/multivariate-statistics` | Completed Bivariate Statistics run and its selected-ISIN set | Project-scoped multivariate result when configured | Reserves the portfolio-level analysis boundary; it does not alter upstream selections or simulate portfolio results. |

The route registry in `apps/web/src/routes.tsx` records the owning module for
every browser page. Each module's browser-to-API contract lives in
`apps/web/src/api/`: `metadata-builder.ts`, `univariate-statistics.ts`, and
`bivariate-statistics.ts`. Shared transport, project context, and workflow
navigation remain in `client.ts`. The workflow contract exposes exactly the
four module stages above. `univariate_selection` is an output artifact owned by
Univariate Statistics, never a separate module or browser stage.

Multivariate Statistics is visible in the sidebar after Bivariate Statistics
and unlocks only when the Bivariate run is complete. Its initial page exposes
the pinned Bivariate run and Univariate selection; it does not offer a synthetic
compute action before the project-scoped multivariate service exists.

## Adding a module

Add a module only when it has a distinct persisted input/output contract. Create
its typed API facade, register its routes with a new `WorkflowModuleId`, persist
the output that the next module consumes, add the corresponding UI specification,
and test every facade route against `apps/web/api-contracts.json`. A later module
must consume upstream persisted IDs rather than browser memory.
