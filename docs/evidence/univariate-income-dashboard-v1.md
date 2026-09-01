# Univariate income dashboard v1 QA evidence

## Table of contents

- [Workflow](#workflow)
- [Fixture and invariants](#fixture-and-invariants)
- [Browser and read plane](#browser-and-read-plane)
- [Sanitization](#sanitization)

## Workflow

The final contract is Metadata full universe → Univariate v3 rows → compact metric
distributions → read-only metric filtering → committed Selection → existing
Bivariate handoff. Nightly refresh remains the single `20:00 Europe/Vienna`
trigger; a stale watermark is a no-op and a newer watermark publishes one coherent
v3 revision.

## Fixture and invariants

The fixture covers monthly, quarterly, growing, cut and irregular distributions,
tail risk, drawdowns, rolling values, shape statistics and typed unavailable
states. An independent row oracle verifies every catalog metric, exact row count,
one matching `univariate.metric_distributions@v1` artifact, and category/summary
reconciliation. Numeric predicates use full-precision anchors; categories use OR
within a metric and metrics use AND across families.

## Browser and read plane

The READY page exposes one reachable card per catalog metric, with semantic
60% plot / 30% summary / 10% selector geometry on desktop and plot → table →
selector stacking on mobile. Fixtures run at 1440×900, 1024×768 and 390×844;
callbacks remain bounded and never hydrate the complete row artifact. Unapplied
filters, plot/accordion interaction, reload and project switching are read-only.

## Sanitization

The immutable `univariate-income-dashboard-v1` record contains the exact 40-hex
Git SHA, contract/registry versions, fixture sizes, registry fingerprint, nightly,
browser, oracle and Bivariate-handoff references. It contains no credentials,
DSNs or private market rows; skipped or cancelled checks are not PASS.
