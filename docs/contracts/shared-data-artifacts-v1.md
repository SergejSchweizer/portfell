# Shared data artifacts v1

## Contents

- [Namespaces](#namespaces)
- [Publication](#publication)
- [Verification](#verification)
- [Filesystem assumptions](#filesystem-assumptions)

## Namespaces

The data share contains exactly four final namespaces:

```
market/       metadata and market snapshots
univariate/   per-ISIN metrics
bivariate/    pair metrics and matrices
multivariate/ portfolios and decisions
```

The gateway cannot publish an artifact. Each stage owns only its namespace.

## Publication

`ArtifactStore.publish_bytes` writes content to a same-directory temporary
`.part` file, flushes and fsyncs it, atomically replaces the final data file,
then publishes a JSON manifest. The manifest records owner, schema version,
SHA-256 hash, byte size, row count, relative path, status and UTC publication
time. Publishing identical bytes under an existing ID is idempotent; different
bytes raise `artifact_identity_conflict`.

## Verification

Readers accept only `published` manifests in the requesting owner's namespace.
They reject unknown contract versions, owner/path mismatches, symlink/path
escapes, size mismatches, hash mismatches and incomplete files. Temporary files
are not addressable through the reader API.

## Filesystem assumptions

The root must be a local filesystem or a mounted NAS that supports atomic
same-directory rename and durable fsync. Deployment preflight must verify that
the configured root is not a symlink and that each namespace is writable by its
own worker. PostgreSQL stores the authoritative manifest record in PR409's
owner schema; this adapter verifies the filesystem half of that contract.
