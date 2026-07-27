# Report Window

## Identity

- Route: `/projects/:projectId/report`
- Funnel stage: Report
- Shared layout: authenticated header and footer

## Purpose

Present the explainable Camovar assessment, selected and excluded instruments, target portfolio, evidence, assumptions, limitations, and Flatex-oriented trade preparation without executing orders.

## Server-owned inputs

Completed portfolio and validation runs, recommendation sections, target weights, risk contributions, income, drawdown, costs, stress results, exclusions, assumptions, warnings, current positions, estimated trades, rounding, fees, taxes where configured, residual cash, and authorized report artifacts.

## Layout and states

Provide assessment summary, passed checks, warnings, portfolio composition, evidence sections, exclusion rationale, assumptions and limitations, current-versus-target comparison, trade-preparation table, download actions, and loading/generating/complete/failed/stale/expired states.

## User actions

Inspect report sections, download authorized HTML or PDF, configure permitted trade-preparation inputs, regenerate when inputs changed, export trade rows, and acknowledge explicit no-order-execution language.

## Acceptance

- [ ] Report content includes selected and excluded instruments with reasons, weights, risks, income, drawdown, costs, stresses, assumptions, and warnings.
- [ ] Whole-share rounding, minimum trade size, fees, taxes, and residual cash are clearly separated from target weights.
- [ ] No action creates or transmits a broker order.
- [ ] Repeated generation for unchanged completed inputs reuses the authorized report artifact.
- [ ] Stale or expired reports cannot be mistaken for current recommendations.

## Security

Downloads require a current authenticated user-owned run and opaque authorized route. Reports and exports exclude provider secrets, session data, internal paths, database ids, hidden cross-user content, and raw exceptions.

## Components and tests

Use approved AssessmentSummary, ReportSection, PortfolioTable, ExclusionTable, EvidenceSummary, AssumptionList, TradePreparationTable, DownloadMenu, StaleBanner, and NoExecutionNotice components. Cover generation, authorized download, stale run, whole-share rounding, insufficient cash, costs and taxes, export, and no-execution fixtures.
