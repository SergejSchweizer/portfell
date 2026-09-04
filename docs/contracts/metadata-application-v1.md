# Metadata application v1

## Contents

- [Boundary](#boundary)
- [Public surface](#public-surface)
- [Isolation](#isolation)
- [Deployment](#deployment)

## Boundary

Metadata is composed by `portfell.services.metadata.MetadataApplication`. Its
only injected dependency is the `MetadataPort` adapter. It owns filtering,
universe publication and metadata history; it does not import analytical stage
implementations.

## Public surface

The process exposes `/metadata` through the host shell, `/api/metadata/*` for
metadata operations and `/health` for readiness. The router returns safe public
error envelopes through the shared HTTP adapter.

## Isolation

```
browser -> metadata application -> MetadataPort -> metadata PostgreSQL schema
                                      |
                                      +--> ID-only workflow command
```

No Metadata callback reads a sibling implementation package or calls a sibling
HTTP endpoint. Downstream work starts only after the Metadata universe is
published.

## Deployment

The application can be started with a MetadataPort backed by PostgreSQL and the
shared market-data artifact store while sibling processes are stopped. Docker
image and health checks are required when this entry point is wired into a
runtime composition.
