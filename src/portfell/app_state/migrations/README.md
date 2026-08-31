# `portfell_dash` migration boundary

## Table of contents

1. [Migration target](#migration-target)
2. [Forward migration](#forward-migration)
3. [Destructive rollback](#destructive-rollback)
4. [Runtime privileges](#runtime-privileges)

## Migration target

The migration target is database `portfell_dash`, schema `portfell`. Migrations in this directory are independent of the legacy Portfell hosted schemas and never read or copy legacy rows.

## Forward migration

Forward migration is the normal operation and is repeat-safe through `portfell.schema_migrations` checksum records. A recorded version whose checksum differs from the checked-in migration fails closed.

## Destructive rollback

Rollback to zero is intentionally **destructive** because v1 application-state revisions are immutable research evidence. `rollback_to_zero` therefore requires `allow_destructive=True`; it drops only schema `portfell` in the already-selected `portfell_dash` database. Production rollback uses the separately documented application/backup cutover process and must never point this migration runner at the legacy Portfell database or at `xetra_loader`.

## Runtime privileges

The runtime LOGIN does not require PostgreSQL superuser privileges. Provisioning grants only database CONNECT plus schema USAGE and table SELECT/INSERT/UPDATE to the configured application role. DELETE is not part of the normal runtime grant contract; immutable tables additionally reject update/delete through database triggers where appropriate.
