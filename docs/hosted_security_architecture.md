# PostgreSQL Hosted Security Architecture


## Table Of Contents

- [Purpose](#purpose)
- [Trust Boundaries](#trust-boundaries)
- [Hosted Runtime Contract](#hosted-runtime-contract)
- [Operations Boundary](#operations-boundary)
- [Historical Hosted PR Evidence](#historical-hosted-pr-evidence)

Last reviewed: 2026-08-04

## Purpose

Portfell runs with PostgreSQL as its only control-plane authority and an immutable shared-market store as its only market-payload plane. The API establishes a request-scoped tenant identity before every database operation; PostgreSQL row-level security enforces that scope. Projects own immutable selection metadata and analytical-run records, while shared market revisions are never copied into project workspaces.

## Trust Boundaries

```text
browser
  |
  | authenticated API requests
  v
web app --------------+
  |                   |
  | API proxy         | no secrets or direct lake access
  v                   |
api service           |
  |                   |
  | request-scoped tenant identity
  v                   |
postgresql with RLS   |
  |                   |
  | catalog records, projects, selections, runs, audit records
  v                   |
shared immutable store <---- EODHD provider
  ^
  |
external KEK secret mount
```

- **Browser** owns presentation and transient interaction state. It must not store EODHD keys, ciphertext, credential fingerprints, internal paths, or sensitive API responses in browser storage or URLs.
- **Web app** owns route and presentation state. It proxies API requests and performs no financial calculations, credential storage, provider calls, or direct lake reads.
- **API service** owns validation, credential handling, workflow orchestration, and audit events. It provisions the configured principal and opens one transaction-scoped RLS context for each request.
- **PostgreSQL** owns users, credentials, projects, immutable selections, durable jobs, workflow settings, analytical-run metadata, and audit records. Every user-scoped table is protected by RLS.
- **External key-encryption key** remains outside Git, container images, CI artifacts, logs, and database backups.
- **Shared immutable store** retains normalized provider observations and derived artifacts without granting browser-side direct access.

## Hosted Runtime Contract

The API container starts only through the PostgreSQL runtime factory. It rejects the retired `local` authority. Shared data is read from published immutable revisions, and only the internal bootstrap worker or the scheduled operations refresh service receives the EODHD operations credential.

Plaintext EODHD keys must never enter source control, browser state, logs, or persisted API responses. The following are forbidden: global current-selection pointers, per-user market grants, local workspace JSON files, and project-specific market-payload copies. Workflow state is derived from PostgreSQL records and published shared revisions.

Public-hosted mode without an authenticated, user-key-backed principal is not supported.

Historical migrations remain immutable so existing migration checksums stay valid.

## Operations Boundary

The operations credential is mounted only into `project-bootstrap-worker` and the one-shot `shared-market-refresh` operations service. Both are on the internal Compose network and publish atomically to the shared store. API and Web containers never receive the operations token.

## Historical Hosted PR Evidence

This table is implementation history. PR156 through PR167 supersede user-grant, local-workspace, and per-user snapshot assumptions while retaining credential encryption, tenant isolation, and content-addressed physical reuse.

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
