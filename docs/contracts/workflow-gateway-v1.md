# Workflow gateway v1

## Contents

- [Responsibilities](#responsibilities)
- [Routing](#routing)
- [Workflow projection](#workflow-projection)
- [Failure isolation](#failure-isolation)

## Responsibilities

The gateway owns public routing, the shared shell boundary, health aggregation
and a bounded workflow read projection. It owns no financial calculation,
analytical repository or artifact write capability.

## Routing

```
gateway /metadata     -> Metadata application
gateway /univariate   -> Univariate application
gateway /bivariate    -> Bivariate application
gateway /multivariate -> Multivariate application
```

Each prefix is mounted once. The public browser routes and API prefixes remain
unchanged inside the mounted applications.

## Workflow projection

`/api/workflow` returns persisted IDs, counts and status only. It does not load
quote rows, metric rows, pair matrices or portfolio artifacts.

## Failure isolation

If an analytical application is unavailable, its route reports a module-local
failure while gateway health and unrelated mounted applications remain live.
