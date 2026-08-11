# Hosted Readiness


## Table Of Contents

- [D017 Provider License](#d017-provider-license)
- [Historical D016 EODHD Storage And Derived Display Rights](#historical-d016-eodhd-storage-and-derived-display-rights)
- [Historical D016 Personal License Boundary](#historical-d016-personal-license-boundary)
- [Historical D016 Shared Physical Deduplication](#historical-d016-shared-physical-deduplication)
- [Historical D016 User Key Backed Grants](#historical-d016-user-key-backed-grants)
- [Retention And Account Deletion](#retention-and-account-deletion)
- [GDPR Rights And Country Coverage](#gdpr-rights-and-country-coverage)
- [Audit Retention And Incident Response](#audit-retention-and-incident-response)
- [Encrypted Backups And Restore Drills](#encrypted-backups-and-restore-drills)
- [KEK Recovery And Rotation](#kek-recovery-and-rotation)
- [Database Role Review](#database-role-review)
- [No Automatic Broker Execution](#no-automatic-broker-execution)

Last reviewed: 2026-08-10

This document is evidence for `docs/security/hosted_readiness.json`. The JSON file is the machine-readable gate input; this file explains the decisions in operational language.

The entitlement model below records D016 evidence and is superseded as a production target by D017.
Public hosting remains blocked until PR156 replaces the machine-readable licensing evidence and
PR167 completes the PostgreSQL/shared-storage cutover gate after PR166 recovery rehearsal.

## D017 Provider License

The authorized provider-license decision approves cross-customer storage, derived-artifact reuse,
retention after project deletion, and operations-credential ingestion. User-provided credentials are
encrypted tenant metadata only and never authorize or feed the globally shared corpus. The versioned
[D017 ownership matrix](shared_data_plane.json) assigns tenant/control data and tenant-neutral
payloads to separate planes and forbids authorization, credential, project, run, session, and user
fields in shared payloads.

## Historical D016 EODHD Storage And Derived Display Rights

Public-hosted mode may store only data fetched through a user-provided EODHD credential and may expose derived views only to users whose immutable entitlement snapshot includes the source observations. Provider redistribution and display rights must be reviewed again before public-hosted mode is enabled for external users.

## Historical D016 Personal License Boundary

Portfell does not pool one maintainer-owned provider key for all users. Each hosted user supplies their own provider credential, and provider calls resolve the credential only at request time through the encrypted vault.

## Historical D016 Shared Physical Deduplication

Shared observations and analytical artifacts may be physically deduplicated, but physical presence never grants visibility. User access is always resolved through user grants, immutable snapshots, and analysis-run ownership.

## Historical D016 User Key Backed Grants

No observation becomes visible to a user until a successful provider run using that user's active credential returns the observation and publishes a user grant.

## Retention And Account Deletion

Account deletion removes user grants, current snapshot pointers, projects, selections, analysis references, and hosted API state. Shared physical observations may remain only as unowned cache material unless a separate legal retention policy requires removal.

## GDPR Rights And Country Coverage

Privacy requests require identity verification, scoped export of user-owned records, deletion of user-owned state, and a country-specific review before public-hosted operation expands beyond the initially approved geography.

## Audit Retention And Incident Response

Hosted audit events must use redacted structured fields, exclude provider keys and tokens, and be retained only for the approved operational period. Incident response must include credential revocation, session revocation, key rotation, and user notification review.

## Encrypted Backups And Restore Drills

Database and shared-store backups must be encrypted. Backup ciphertext and KEK recovery material are stored separately. Restore drills must prove that missing KEK versions fail closed rather than exporting decrypted provider keys.

## KEK Recovery And Rotation

Credential KEKs are external runtime secrets. Rotation rewraps credentials without logging plaintext. Recovery material is separated from database/shared-store backups and must not enter Git, images, CI, logs, or browser storage.

## Database Role Review

Hosted persistence uses least-privilege roles and row-level security for user-owned tables. API access is through repository boundaries, not direct browser or Web-container database access.

## No Automatic Broker Execution

Portfell may produce broker-ready order files and recommendations, but hosted mode must not place broker orders automatically. Human approval remains outside the hosted API execution boundary.
