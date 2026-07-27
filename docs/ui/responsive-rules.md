# Responsive Rules

## Viewports

- Desktop: wide shell with visible navigation and side-by-side controls where useful.
- Tablet: stacked navigation and content with preserved task order.
- Mobile: single-column flow with readable labels and accessible controls.

## Rules

1. Navigation may collapse, but route order must remain intact.
2. Important actions must remain reachable without hover.
3. Tables may scroll horizontally, but column meaning must remain visible.
4. Charts must retain an accessible textual alternative.
5. Sidebar resizers or split panes may be removed below defined breakpoints if task completion remains intact.

## Breakpoint contract

Responsive breakpoints are versioned in design tokens and documented in page specs. A page spec is incomplete if it does not state what happens at desktop, tablet, and mobile widths.

