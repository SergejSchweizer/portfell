# Sunday Full Research Refresh

Last reviewed: 2026-08-20.

The managed schedule is exactly:

```text
CRON_TZ=Europe/Vienna
0 9 * * 0
```

The schedule is embedded in the existing long-running `project-bootstrap-worker`; no browser and no fourth Compose service are permitted. `SundayWorkerSchedule` supplies due-time calculation with `zoneinfo` and `run_sunday_cycle` uses a non-blocking `flock` to prevent overlapping cycles.

One logical cycle performs exactly one de-duplicated active-project market refresh for quotes, dividends and splits, followed by each active project in stable slug order. Each project reuses the same manual Univariate -> Bivariate -> Multivariate service contracts, persisted objective/constraints, DecisionArtifacts, ResearchUniverseSnapshots and logical-run identities. Only an absent objective defaults to `return_risk`.

Project failures do not stop other projects. A failed Univariate blocks only that project's Bivariate and Multivariate stages; a failed Bivariate blocks only that project's Multivariate stage. Re-running the same immutable inputs must reuse existing market business keys and analytical logical runs.

Operational output is count-only and must not include credentials, provider tokens, database URLs, raw financial series or decision payloads.
