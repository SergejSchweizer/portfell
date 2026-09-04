# Independent modules closeout audit v1

## Contents

- [Purpose](#purpose)
- [Current result](#current-result)
- [Required cutover](#required-cutover)
- [PASS criteria](#pass-criteria)

## Purpose

PR427 is the final removal of the transitional monolith. The audit scans
production Python for the old cross-stage `ResearchApplicationService` and
`mount_dash_app` composition markers.

## Current result

The audit intentionally reports `BLOCKED` while those markers remain. This
prevents publishing a false independent-modules PASS. It contains only relative
source locations, contract version and migration version; no credentials or
market rows.

## Required cutover

Move the runtime composition and callback ownership into the gateway and the
four service entrypoints. Update refresh workers and tests to use module-local
ports, then delete the old composition paths. Re-run this audit before removing
the transitional branch.

## PASS criteria

The result may become `PASS` only when the reference list is empty and the
isolated module REST, PostgreSQL, Playwright, resilience and full-workflow gates
all pass on the same Git/image heads.
