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

## Header Metadata Fetch

The persistent header contains the EODHD key input and `Fetch all metadata`
action. While the server-owned metadata request is active, a narrow determinate
progress bar appears directly below the key input and the action is disabled.
The browser polls the metadata-run status endpoint and renders its completed
exchange count and percentage.

For the trusted local workspace runtime, an existing EODHD credential is
decrypted server-side for the stable workspace user and prefilled into the
visible header field after a reload. The browser keeps that value only in React
state; it does not write the provider key to cookies, local storage, or session
storage.

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

The sidebar remains a flat `272px` surface separated from main content by one
border. Long project names truncate in the selector without changing its width;
the native control exposes the complete name through its title.

## Mobile Drawer

At widths of `900px` and below, the persistent sidebar is replaced with one
header menu control named `Open project navigation`. The same `ProjectSidebar`
instance becomes a left drawer with a width of `min(320px, 88vw)`; there is no
second project selector or workflow list.

Opening the drawer moves focus to the project selector, or the first available
workflow link when no selector is available. Focus remains in the drawer until
it closes. Escape, the backdrop, a successful project switch, and route changes
close it and return focus to the menu control. While open, background scrolling
is disabled. The drawer transition is removed for reduced-motion users.

## Project Switch

After a successful project switch, the shell refreshes the selected project's
workflow and sends one typed update to the four route pages. Pages clear their
transient selections, results, progress, and errors before loading replacement
server-owned data. Metadata Filter additionally loads saved field values through
`GET /api/projects/{project_id}/metadata-filter`. A failed switch keeps the prior
project and route intact.

## Boundaries

The sidebar may render project names and workflow status. It must not render
project ids, provider credentials, storage paths, authorization decisions, or
unscoped data. Mobile drawer behavior is defined by PR119.