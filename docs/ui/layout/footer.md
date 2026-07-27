# Global Footer

## Purpose

Provide stable application metadata, legal or readiness links, version context, and non-primary support information without competing with the active research workflow.

## Variants

- Public or unauthenticated footer.
- Authenticated application footer.
- Minimal footer for narrow or workflow-dense layouts.

## Required content

- Camovar product name.
- Application version or build identifier where available.
- Links to privacy, terms, licensing or hosted-readiness information where enabled.
- Clear statement that Camovar prepares research and trades but does not execute broker orders automatically where relevant.
- Environment indicator only for non-production environments.

## Behaviour

The footer contains no page-specific primary action and performs no implicit network request. Links preserve authenticated safety boundaries and must not leak route parameters or internal identifiers.

## Acceptance

- [ ] Footer variants render consistently on all registered windows.
- [ ] Footer content does not obscure tables, charts, forms, dialogs, or mobile actions.
- [ ] Build and environment labels are accurate and deterministic.
- [ ] Legal and readiness links are keyboard accessible.
- [ ] No window reimplements the global footer.

## Security

The footer must not expose deployment secrets, internal hostnames, storage paths, database details, provider credentials, session data, commit metadata not intended for users, or diagnostic payloads.

## Accessibility

Use a semantic content-info landmark, descriptive link labels, visible focus, and sufficient contrast. Repeated navigation must remain concise and understandable to screen-reader users.

## Responsive behaviour

Desktop may use one horizontal row. Tablet and mobile may stack content, but legal links, version context, and the no-order-execution statement remain readable without horizontal scrolling.
