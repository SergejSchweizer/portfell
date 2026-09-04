# Module least privilege v1

## Contents

- [Roles](#roles)
- [Rights](#rights)
- [Secrets](#secrets)
- [Filesystem](#filesystem)

## Roles

The deployment has one login role per process: `portfell_gateway`,
`portfell_metadata`, `portfell_univariate`, `portfell_bivariate` and
`portfell_multivariate`.

## Rights

```
gateway      -> workflow commands (read/write)
metadata     -> metadata schema (read/write)
univariate   -> univariate schema (read/write), metadata published reads
bivariate    -> bivariate schema (read/write), univariate published reads
multivariate -> multivariate schema (read/write), bivariate published reads
```

No role receives `GRANT ALL`, superuser, cross-stage write or public-table
rights. The migration is idempotent and grants only explicit owner tables.

## Secrets

Role passwords are provisioned by the operator through external secret files;
they are never embedded in Compose, source, logs or test evidence.

## Filesystem

Workers use the shared data root with least-privilege mounts. Read-only
consumers cannot publish or overwrite another module's namespace.
