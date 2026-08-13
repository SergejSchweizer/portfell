# Portfell Design System


## Table Of Contents

- [Principles](#principles)
- [Tokens](#tokens)

## Principles

Portfell puts content before decoration. Each task region has one clear primary
action, uses progressive disclosure, follows familiar platform behavior, keeps
financial work readable at operational density, and shows system status visibly.
Direct manipulation is used only for reversible actions. Decorative elements
must not compete with financial data.

## Tokens

All production values are declared once in `apps/web/styles/app.css`.

| Token | Use | Contrast and prohibited use |
| --- | --- | --- |
| `canvas` | Application background | Never a tinted page-wide treatment. |
| `surface` | Primary control and content surface | Meets AA contrast with `text`. |
| `surface-subtle` | Quiet selected or secondary surface | Not a status-only signal. |
| `text` / `text-muted` | Primary and supporting text | Text meets AA contrast against its surface. |
| `border` / `border-strong` | Separation and focus-adjacent boundaries | Not a substitute for focus. |
| `accent` / `accent-hover` | Primary actions and current navigation | One restrained blue accent only. |
| `focus` | Keyboard focus outline | At least 2px with separation from the control edge. |
| `success`, `warning`, `danger` | Matching status and destructive action | Always paired with visible text or shape. |
| `disabled` | Disabled controls | Never used for readable locked status text. |
| `progress-height` | Native computation progress thickness | Fixed at 10px; progress tracks remain full width. |

Typography uses the platform UI stack, sizes 12, 14, 16, 20, and 28px, line
heights of at least 1.35, zero letter spacing, and weights 400, 500, 600, or
700. Spacing uses a 4px base: 4, 8, 12, 16, 24, 32, and 48px. Radius values are
4, 6, and 8px only. Shadows are reserved for floating surfaces.

No gradients, glass effects, decorative blobs, remote font CDNs, proprietary
platform branding, or color-only statuses are permitted.
