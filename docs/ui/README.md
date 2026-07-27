# Camovar UI Specifications

This directory is the canonical specification source for the Camovar Web UI.

## Structure

- `layout/header.md`: global authenticated and unauthenticated header contract.
- `layout/footer.md`: global footer contract.
- `windows/`: one Markdown specification per UI window or route-level screen.
- `templates/window-spec-template.md`: mandatory structure for new window specifications.

## Rules

1. Every production UI window must have exactly one specification file in `windows/`.
2. Header and footer behaviour must be specified only in `layout/` and referenced from window files rather than duplicated.
3. A registered route without a corresponding window specification fails documentation validation.
4. Window files define presentation, interaction, API contracts, states, accessibility, responsive behaviour, security constraints, and acceptance criteria.
5. Financial calculations, authorization decisions, provider credentials, internal paths, and unrestricted artifact identifiers remain server-side and must not be specified as browser responsibilities.
6. Codex changes to one window should normally update only its specification, dependent shared-layout specifications, implementation, and tests.

## Window registry

| Window | Specification |
|---|---|
| Login | `windows/login.md` |
| Dashboard | `windows/dashboard.md` |
| Projects | `windows/projects.md` |
| Data | `windows/data.md` |
| Metadata | `windows/metadata.md` |
| Univariate | `windows/univariate.md` |
| Filter | `windows/filter.md` |
| Diversification | `windows/diversification.md` |
| Portfolio | `windows/portfolio.md` |
| Validation | `windows/validation.md` |
| Report | `windows/report.md` |
| Settings | `windows/settings.md` |
| Account | `windows/account.md` |

New route-level windows must be added to this registry in the same PR that introduces the route.
