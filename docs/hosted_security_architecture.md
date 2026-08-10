# Local Workspace Security Architecture

Last reviewed: 2026-08-04

## Purpose

Portfell currently runs as one local workspace. It has no end-user authentication provider, browser session, callback route, or public multi-user deployment boundary. The local analytical core, encrypted EODHD credential handling, deterministic workflow state, and three-module Web workspace remain available.

Public hosting is disabled until a replacement identity and authorization architecture is explicitly designed, implemented, and reviewed.

## Trust Boundaries

```text
browser
  |
  | local workspace API requests
  v
web app --------------+
  |                   |
  | API proxy         | no secrets or direct lake access
  v                   |
api service           |
  |                   |
  | fixed local workspace identity
  v                   |
postgresql with RLS   |
  |                   |
  | catalog records, grants, runs, audit records
  v                   |
shared immutable store <---- EODHD provider
  ^
  |
external KEK secret mount
```

- **Browser** owns presentation and transient interaction state. It must not store EODHD keys, ciphertext, credential fingerprints, internal paths, or sensitive API responses in browser storage or URLs.
- **Web app** owns route and presentation state. It proxies API requests and performs no financial calculations, credential storage, provider calls, or direct lake reads.
- **API service** owns validation, credential handling, workflow orchestration, audit events, and the fixed local-workspace identity. Browser headers and cookies cannot select a different user.
- **PostgreSQL** owns catalog, credential, project, grant, snapshot, analysis, artifact, and audit records. Existing user-scoped tables retain RLS to keep a future identity boundary possible.
- **External key-encryption key** remains outside Git, container images, CI artifacts, logs, and database backups.
- **Shared immutable store** retains normalized provider observations and derived artifacts without granting browser-side direct access.

## Local Runtime Contract

The API resolves every request to the `user-a` local workspace. State-changing requests require no CSRF token because there is no browser session or cross-user boundary. The application must only be exposed to trusted local networks while this mode is active.

Plaintext EODHD keys must never enter source control, browser state, logs, or persisted API responses. global current-selection pointers remain forbidden; workflow state is derived from local workspace records. Public-hosted mode remains disabled until the hold below is lifted.

The catalog migration `remove_google_authentication` drops retired identity and session tables from existing local volumes. Historical migrations remain immutable so existing migration checksums stay valid.

## Public Hosting Hold

Do not enable public deployment while this contract is active. A future hosted design must introduce a reviewed identity provider, authorization model, session strategy, migration plan, threat model, and public readiness evidence before any internet-facing release.

## Historical Hosted PR Evidence

This table is implementation history, not the D017 production target. PR156 through PR167 supersede
the user-grant and per-user snapshot authorization assumptions while retaining credential encryption,
tenant isolation, and content-addressed physical reuse.

| Requirement | PR |
| --- | --- |
| Architecture decision, threat model, and prohibited designs | PR84 |
| PostgreSQL catalog, roles, migrations, and RLS | PR85 |
| Google-only OIDC and server-side sessions | PR86 |
| Encrypted EODHD credential vault and KEK rotation | PR87 |
| Shared content-addressed market observation store | PR88 |
| User grants, provenance, and immutable snapshots | PR89 |
| User-key-backed ingestion and refresh planning | PR90 |
| Scoped analytical input boundary and local adapter compatibility | PR91 |
| Content-addressed univariate and return artifact cache | PR92 |
| Content-addressed bivariate cache and exact alignment | PR93 |
| Content-addressed portfolio, backtest, and report artifacts | PR94 |
| Docker Compose hosted development runtime | PR95 |
| FastAPI user, credential, download, project, and analysis API | PR96 |
| Google-authenticated Web UI and research funnel | PR97 |
| Public-repository CI, supply-chain, and deployment hardening | PR98 |
| Licensing, privacy, retention, backup, restore, and key-rotation readiness | PR99 |
| End-to-end hosted cutover and multi-user proof | PR100 |
