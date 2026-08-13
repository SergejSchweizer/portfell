# Project Sidebar


## Table Of Contents

- [Inputs](#inputs)
- [Header Metadata Fetch](#header-metadata-fetch)
- [Required States](#required-states)
- [Desktop Layout](#desktop-layout)
- [Mobile Drawer](#mobile-drawer)
- [Project Switch](#project-switch)
- [Boundaries](#boundaries)

The application sidebar is driven by the server-owned project context. It does
not create, sort, authorize, or persist projects in the browser.

## Inputs

- `GET /api/project-context` supplies the selected project, the canonical
  project list, and each project's active-run status.
- `PUT /api/project-context/current-project` changes the selected owned project.
- `GET /api/projects/{project_id}/workflow` supplies the persisted workflow statuses
  for the selected project.
- `workflowPages` in `apps/web/src/routes.tsx` remains the only workflow route
  registry.
- Canonical workflow URLs use `/projects/{project-name-slug}/{workflow-page}`.
  The browser resolves the readable name slug to the owned project held in the current context;
  the internal project id remains restricted to API requests.

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
- Empty: show `No projects yet`; only Metadata Builder is available.
- Ready: show the selected project's name and the four-module hierarchy.
- Switching: disable the selector while the request is active.
- Error: retain the previously selected project and announce the recoverable
  error without replacing page content.

## Desktop Layout

At viewport widths above `900px`, the sidebar is one persistent `272px` left
column below the header. Its first control is the native project selector. The
workflow below it is an ordered hierarchy derived exclusively from
`workflowPages`: Metadata Builder, Univariate Statistics, Bivariate Statistics, and Multivariate
Statistics. The active stage uses `aria-current="page"`; locked
stages remain visible, include text status, and are non-links with
`aria-disabled="true"`.

Workflow status text uses consistent visual cues: `Complete` is green, `Ready` is blue, and `Locked`
is grey. The status words remain visible text so their meaning does not depend on color alone.

Available workflow links use client-side History navigation. A normal click updates the canonical
URL and swaps only the route content without reloading the document, shell, header, or sidebar.
Modified clicks retain native link behavior for opening a new tab or window. Workflow and project
context revalidation runs in the background and retains the last successful shell data until the
replacement response arrives.

The sidebar remains a flat `272px` surface separated from main content by one
border. Project option text remains only the project name. A project with a
running run uses the `success` color; a waiting run uses the `danger` color;
inactive projects use the normal text color. The selected project uses the same
status color in the closed selector. Long project names truncate without changing
the selector width; the native control exposes the complete name through its title.

## Mobile Drawer

At widths of `900px` and below, the persistent sidebar is replaced with a
header-native `Current project` selector and one header menu control named
`Open project navigation`. The selector always contains every project returned
by the server-owned context and uses the same project-switch request as the
desktop sidebar. The `ProjectSidebar` instance becomes a left drawer with a
width of `min(320px, 88vw)`; the workflow list remains only in that drawer.

Opening the drawer moves focus to the project selector, or the first available
workflow link when no selector is available. Focus remains in the drawer until
it closes. Escape, the backdrop, a successful project switch, and route changes
close it and return focus to the menu control. While open, background scrolling
is disabled. The drawer transition is removed for reduced-motion users.

## Project Switch

After a successful project switch, the shell refreshes the selected project's
workflow and sends one typed update to the four route pages. Pages clear their
transient selections, results, progress, and errors before loading replacement
server-owned data. Metadata Builder additionally loads saved field values through
`GET /api/projects/{project_id}/metadata-builder`. A failed switch keeps the prior
project and route intact.

Opening a canonical project URL activates that owned project before its workflow
state is rendered. Legacy workflow-only URLs remain valid and are replaced with
the canonical project URL after context loads. Renaming a project changes its
canonical URL slug; shared links should use the current project name.

The application shell uses client-side history navigation for every ordinary
internal-link click, so the current shell remains responsive while destination
pages load their server-owned data. Modified and external-link clicks retain
normal browser behavior.

## Boundaries

The sidebar may render project names and workflow status. It must not render
project ids, provider credentials, storage paths, authorization decisions, or
unscoped data. Mobile drawer behavior is defined by PR119.
