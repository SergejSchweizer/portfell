# Account Window

## Identity

- Route: `/account`
- Funnel stage: none
- Shared layout: authenticated header and footer

## Purpose

Show authenticated identity and account state, support logout and account deletion, and explain the consequences for credentials, grants, projects, snapshots, analyses, reports, and retained shared physical data.

## Server-owned inputs

Verified identity display fields, authentication provider, session summary, account-created metadata, deletion eligibility, retention and licensing notices, and redacted operation status.

## Layout and states

Provide identity summary, session and provider context, privacy and retention information, logout action, account-deletion section, consequences summary, confirmation workflow, and loading/ready/deleting/deleted/failed/re-authentication-required states.

## User actions

Logout, review privacy and retention information, begin deletion, confirm deletion with required recent authentication, cancel deletion, and complete the terminal signed-out state.

## Acceptance

- [ ] Logout revokes or terminates the active session and does not delete account data.
- [ ] Account deletion explains irreversible effects before confirmation.
- [ ] Successful deletion removes user credentials and grants according to policy without deleting shared objects still referenced by others.
- [ ] Deleted users cannot navigate back into authenticated content through browser history or cache.
- [ ] Failure states are redacted, recoverable where safe, and do not leave ambiguous deletion status.

## Security

Identity fields are sourced from the authenticated server session. Session tokens, Google tokens, provider credentials, ciphertext, internal ids, paths, and other users' retention references are never displayed. Deletion requires CSRF protection and recent authentication.

## Components and tests

Use approved IdentityCard, SessionSummary, PrivacyNotice, RetentionSummary, LogoutButton, DangerZone, DestructiveConfirmDialog, ReauthenticationNotice, and TerminalState components. Cover logout, cancel, successful deletion, partial service failure, retry, browser history, and re-authentication fixtures.
