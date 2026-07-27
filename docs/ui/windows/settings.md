# Settings Window

## Identity

- Route: `/settings`
- Funnel stage: none
- Shared layout: authenticated header and footer

## Purpose

Manage user-visible application preferences and the EODHD credential lifecycle without exposing stored secret material or changing analytical results implicitly.

## Server-owned inputs

Credential masked status, provider capability, permitted preference values, current non-secret preferences, session freshness where required, environment-safe feature availability, and redacted validation errors.

## Layout and states

Provide credential status and replace/delete controls, display and research defaults where supported, capability summary, save status, warnings, and loading/ready/validating/saved/failed/re-authentication-required states.

## User actions

Set or replace a provider key, validate it, revoke or delete it, update permitted preferences, restore defaults, and navigate to account management.

## Acceptance

- [ ] A stored provider key is never redisplayed after submission.
- [ ] Replace, revoke, and delete actions provide explicit state and confirmation.
- [ ] Unchanged preferences do not create duplicate records or invalidate analyses.
- [ ] Settings that affect analytical inputs clearly state their future scope and do not silently mutate completed runs.
- [ ] Mobile, keyboard, validation-error, and re-authentication flows are covered.

## Security

Credentials exist in browser memory only for the bounded submission flow and are never stored in localStorage, sessionStorage, URLs, logs, analytics, screenshots, traces, or error payloads. Sensitive actions require CSRF protection and recent authentication where policy requires it.

## Components and tests

Use approved SettingsSection, SecretInput, MaskedCredentialStatus, CapabilityCard, PreferenceField, SaveBar, ConfirmDialog, ReauthenticationNotice, and ErrorSummary components. Cover no credential, valid, invalid, replacement, revoke, delete, unavailable key service, unchanged preferences, and failed save fixtures.
