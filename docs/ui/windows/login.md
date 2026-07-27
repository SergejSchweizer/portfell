# Login Window

## Identity

- Route: `/login`
- Funnel stage: none
- Shared layout: public header and footer variants

## Purpose

Authenticate the user through Google OpenID Connect or the explicitly enabled local-development provider and establish a server-side session before any private Camovar state is displayed.

## Server-owned inputs

Session status, permitted authentication providers, environment-safe local-development flag, and redacted authentication errors.

## Layout and states

Show product identity, concise login explanation, provider action, privacy context, and status area. Cover unauthenticated, redirecting, callback-processing, authenticated redirect, provider unavailable, invalid callback, expired state, and local-development variants.

## User actions

Start Google login, use local-development login only when explicitly enabled, retry a recoverable failure, and navigate to public legal information.

## Acceptance

- [ ] Private dashboard or project data is never rendered before successful session establishment.
- [ ] Replayed, expired, malformed, or rejected callbacks show a redacted actionable failure.
- [ ] Local-development authentication is disabled by default outside development and visibly labelled when enabled.
- [ ] Successful repeat login restores the existing user without duplicating identity records.
- [ ] Keyboard, mobile, and screen-reader login paths are covered.

## Security

Tokens, authorization codes, state, nonce, code verifier, session cookie values, client secrets, and raw provider responses are never rendered, logged in browser-visible output, or stored in browser storage.

## Components and tests

Use approved Brand, AuthPanel, Button, StatusMessage, ErrorSummary, and legal-link components. Provide deterministic fixtures and browser tests for every documented state.
