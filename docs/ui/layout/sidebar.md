# Project Sidebar

The application sidebar is driven by the server-owned project context. It does
not create, sort, authorize, or persist projects in the browser.

## Inputs

- `GET /api/project-context` supplies the selected project and the canonical
  project list.
- `PUT /api/project-context/current-project` changes the selected owned project.
- `GET /api/projects/{project_id}/workflow` supplies the four workflow statuses
  for the selected project.
- `workflowPages` in `apps/web/src/routes.tsx` remains the only workflow route
  registry.

## Required States

- Loading: reserve the final sidebar width while context is loading.
- Empty: show `No projects yet`; only Metadata Filter is available.
- Ready: show the selected project's name and the four-stage hierarchy.
- Switching: disable the selector while the request is active.
- Error: retain the previously selected project and announce the recoverable
  error without replacing page content.

## Desktop Layout

At viewport widths above `900px`, the sidebar is one persistent `272px` left
column below the header. Its first control is the native project selector. The
workflow below it is an ordered hierarchy derived exclusively from
`workflowPages`: Metadata Filter, Univariate Statistics, Univariate Filter, and
Bivariate Statistics. The active stage uses `aria-current="page"`; locked
stages remain visible, include text status, and are non-links with
`aria-disabled="true"`.

## Project Switch

After a successful project switch, the shell refreshes the selected project's
workflow and sends one typed update to the four route pages. Pages clear their
transient selections, results, progress, and errors before loading replacement
server-owned data. A failed switch keeps the prior project and route intact.

## Boundaries

The sidebar may render project names and workflow status. It must not render
project ids, provider credentials, storage paths, authorization decisions, or
unscoped data. Mobile drawer behavior is defined by PR119.