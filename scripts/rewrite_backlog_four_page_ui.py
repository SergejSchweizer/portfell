from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "BACKLOG.md"


def section(text: str, start: str, end: str | None) -> str:
    start_index = text.index(start)
    end_index = len(text) if end is None else text.index(end, start_index)
    return text[start_index:end_index].strip()


def split_pr_blocks(value: str) -> tuple[str, list[str]]:
    match = re.search(r"(?m)^### PR", value)
    if match is None:
        return value.strip(), []
    intro = value[: match.start()].strip()
    blocks = [block.strip() for block in re.split(r"(?m)(?=^### PR)", value[match.start() :])]
    return intro, [block for block in blocks if block]


def is_finished(block: str) -> bool:
    lowered = block.lower()
    return any(
        marker in lowered
        for marker in (
            "git status: merged",
            "git status: implemented",
            "git status: closed",
            "final status: merged",
            "final status: implemented",
        )
    )


MINIMAL_UI_STACK = r"""## Active Four-Page Portfell UI PR Stack

This is the canonical UI implementation stack. It supersedes the former eight-stage research-funnel UI plan. The production application has exactly four pages, in this order:

```text
metadata_filter
    -> univariate_statistics
    -> univariate_filter
    -> bivariate_statistics
```

The persistent header contains the EODHD credential input and the metadata refresh action. The canonical Python operation is `fetch_all_metadata`; the removed name `fetch_all_isins` must not be reintroduced as a function, module, command, route, alias, compatibility shim, or documentation term.

The stack is deliberately sequential. Each PR must be independently reviewable, must leave the repository green, and must not implement scope assigned to a later PR. Browser code owns presentation and transient interaction state only. Credentials, authorization, workflow status, selections, calculations, persistence, invalidation, and financial/statistical logic remain server-owned.

### PR110. Canonical Workflow State And Four-Page API Contract

Branch: `feat/four-page-workflow-state`.

Git status: not started. PR: TBD.

Priority: P0 workflow foundation.

Depends on: current `main`.

Scope:

- Add one backend-owned workflow-state model for the current authenticated user and active project.
- Expose `GET /api/workflow` and return exactly these stages: `metadata_filter`, `univariate_statistics`, `univariate_filter`, and `bivariate_statistics`.
- Use only the statuses `locked`, `ready`, `running`, `complete`, `failed`, and `stale`.
- Include immutable upstream identifiers in every completed stage: metadata revision, metadata selection id, quote run id, univariate run id, univariate-filter selection id, and bivariate run id where applicable.
- Define downstream invalidation rules in one backend module. A metadata refresh invalidates every downstream stage; a metadata-filter change invalidates quote loading and every later stage; a univariate-statistics change invalidates the univariate filter and bivariate statistics; a univariate-filter change invalidates bivariate statistics.
- Add matching TypeScript contracts in `apps/web/src/contracts.ts` and one `loadWorkflow()` client function. Pages must not infer completion from local component state.
- Persist or reconstruct workflow status from existing server-owned project, run, selection, and artifact records. Do not add Redux, Zustand, XState, React Router, WebSockets, Celery, Redis, or a generic workflow engine.

Acceptance:

- `GET /api/workflow` returns the same JSON for the same persisted state across repeated calls and process restarts.
- A new user with no metadata receives `metadata_filter=ready` and the other three stages as `locked`.
- Every upstream mutation produces the exact stale/locked transitions defined above.
- The response never exposes an EODHD key, filesystem path, unrestricted global dataset identifier, or another user's state.
- Unit tests cover every allowed status transition and every invalidation edge.
- API tests prove user isolation and deterministic response ordering.
- TypeScript compiles without casts from `unknown` to the workflow-state type.

Security: Workflow state is resolved inside the authenticated user scope and never from unrestricted global lake scans.

Determinism: Identical persisted identifiers and statuses produce byte-equivalent JSON after canonical serialization.

Idempotency: Repeating `GET /api/workflow` performs no writes and creates no projects, runs, selections, or artifacts.

### PR111. Metadata Header, Metadata Filter, And Real Quote Progress

Branch: `feat/metadata-filter-quote-progress`.

Git status: not started. PR: TBD.

Priority: P0 first runnable page.

Depends on: PR110.

Scope:

- Keep the EODHD key input in the persistent header. Submission must call `POST /api/credentials/eodhd`, clear the input, then call the real metadata workflow through `POST /api/metadata/fetch-all`.
- Inject the authenticated user's decrypted key into `run_fetch_all_metadata_workflow`; do not read a shared plaintext key or return the key to the browser.
- Make `/metadata-filter` the default application route and the first workflow page.
- Load multiple-choice values from `GET /api/metadata-filter/options` for exchange, instrument type, country, and currency; include a name-contains input.
- Submit the filter through `POST /api/metadata-filter` and persist a deterministic metadata selection id.
- Place the quote progress bar after all metadata controls and status text. Place a right-aligned `Fetch quotes` button beneath the progress bar.
- Start quote ingestion with `POST /api/quote-runs` using only the current metadata selection id. Poll `GET /api/quote-runs/{run_id}` until complete or failed.
- Return and render `total`, `completed`, `failed`, and integer `percent` values. The progress bar must represent server progress; it must not jump from zero to 100 solely because one HTTP request returned.
- Disable duplicate metadata, filter, and quote submissions while the corresponding operation is running.
- Refresh workflow state after every successful mutation.

Acceptance:

- The header never stores the provider key in URL parameters, browser storage, HTML, logs, screenshots, analytics, or API responses.
- `fetch_all_metadata` performs a mocked provider request in tests and publishes one deterministic metadata revision.
- The filter button remains disabled when all filter fields are empty, unless an explicit `Select all metadata` action is implemented and documented.
- `Fetch quotes` remains disabled until a non-empty metadata selection exists.
- The DOM order is: metadata controls, apply-filter action, selection status, progress label, progress element, progress status, right-aligned `Fetch quotes` action.
- Polling stops on `complete`, `failed`, component unmount, route change, or request cancellation.
- Repeating the same metadata filter returns the same logical selection id.
- Repeating `Fetch quotes` for an already running or completed identical run returns that run instead of creating a duplicate.
- Browser tests cover successful metadata loading, empty metadata, invalid credential, zero-result filter, partial quote failure, complete quote success, refresh recovery, and secret non-disclosure.

Security: Credential decryption is limited to the provider-call boundary; quote entitlements are granted only after a successful user-key-backed request.

Determinism: Canonical filter serialization and metadata revision pinning produce stable selection and quote-run identities.

Idempotency: Retrying credential save, metadata refresh, identical filtering, polling, or quote-run creation does not duplicate logical state.

### PR112. Functional Univariate Statistics Page

Branch: `feat/univariate-statistics-page`.

Git status: not started. PR: TBD.

Priority: P1 second workflow page.

Depends on: PR111.

Scope:

- Replace the current read-only summary page with a complete execution page.
- Add `POST /api/univariate-statistics/runs` with the current metadata selection id and quote run id as required immutable inputs.
- Add `GET /api/univariate-statistics/runs/{run_id}` for status and `GET /api/univariate-statistics/runs/{run_id}/results` for server-paginated results.
- Require quote completion before execution. Render a locked explanation and link to `/metadata-filter` when prerequisites are absent or stale.
- Provide one `Compute univariate statistics` action, running status, cancellation-safe polling, empty state, failure state, completion summary, sorting, and pagination.
- Render at minimum: listing identity, ISIN, symbol, exchange, observation count, annualized return, annualized volatility, Sharpe ratio, maximum drawdown, and expected shortfall when present in the backend artifact.
- Keep units and numerical precision in typed formatter functions; do not calculate statistics in React.
- Remove the old aggregate-only API dependency when no remaining caller uses it.

Acceptance:

- The page cannot start without a complete quote run for the current metadata selection.
- The POST endpoint invokes the real univariate workflow and never returns a synthetic success response.
- Result rows are scoped exactly to the pinned metadata selection and quote dataset.
- Sorting and pagination are server-owned and deterministic for equal values through a stable listing-id tie-breaker.
- Refreshing during a running job restores the same run and progress.
- Repeating an identical request returns the existing running or completed run id.
- Unit tests verify input pinning, selection scoping, failure propagation, deterministic ordering, and no unrestricted Gold/Silver scan.
- Browser tests verify locked, running, empty, failed, complete, paginated, and refreshed-running states.

Security: Results are resolved through the authenticated user's snapshot and entitlement scope.

Determinism: The artifact id includes exact quote inputs, selection membership, parameters, and algorithm version.

Idempotency: Identical run creation is deduplicated by the canonical input hash.

### PR113. Functional Univariate Filter Page

Branch: `feat/univariate-filter-page`.

Git status: not started. PR: TBD.

Priority: P1 third workflow page.

Depends on: PR112.

Scope:

- Replace the placeholder page with a typed predicate editor and persisted selection result.
- Add `GET /api/univariate-filter/metrics` for allowed numerical metrics, labels, units, and valid operators.
- Add `POST /api/univariate-filter` accepting `source_run_id`, optional `selection_name`, and an ordered predicate list with `metric`, `operator`, and numeric `value`.
- Permit only `=`, `!=`, `>`, `>=`, `<`, and `<=` for numerical metrics. Apply all predicates with logical AND.
- Canonically sort predicates for identity generation while preserving the user-visible edit order separately.
- Return `selection_id`, `input_count`, `selected_count`, `excluded_count`, normalized predicates, and exclusion summaries.
- Render add/remove predicate rows, visible validation, apply action, running state, result counts, and a server-paginated selected-listing table.
- Require a completed, non-stale univariate run. Clear stale results immediately when a predicate changes after completion.
- The backend must filter only rows belonging to the pinned source run; it must not read every persisted univariate row.

Acceptance:

- Invalid metrics, operators, non-finite values, empty predicate lists, and duplicate contradictory predicates return structured 4xx errors.
- A valid predicate set selects exactly the rows produced by applying all predicates to the pinned source run.
- `input_count = selected_count + excluded_count` in every successful response.
- Identical normalized predicates on the same source run return the same selection id.
- Predicate order differences do not create duplicate selections.
- The page renders locked, editing, invalid, running, empty-result, failed, complete, and stale states.
- Tests cover all operators, AND semantics, boundary equality, NaN/infinity rejection, source-run isolation, deterministic identity, and duplicate submission.

Security: Metric discovery and filtering operate only on artifacts visible to the authenticated user.

Determinism: Metric definitions, operator semantics, predicate normalization, and selection ordering are versioned.

Idempotency: Reapplying an identical normalized predicate set reuses the same selection and membership rows.

### PR114. Functional Bivariate Statistics Page

Branch: `feat/bivariate-statistics-page`.

Git status: not started. PR: TBD.

Priority: P1 fourth workflow page.

Depends on: PR113.

Scope:

- Replace the placeholder page with pair-plan, execution, progress, and result views.
- Add `POST /api/bivariate-statistics/plan` accepting the current univariate-filter selection id and returning selected listing count, theoretical pair count, configured pair limit, and whether execution is allowed.
- Add `POST /api/bivariate-statistics/runs`, `GET /api/bivariate-statistics/runs/{run_id}`, and `GET /api/bivariate-statistics/runs/{run_id}/results`.
- Fail before pair generation when the theoretical pair count exceeds the configured maximum.
- Poll real server progress using `total_pairs`, `completed_pairs`, `failed_pairs`, and integer `percent`.
- Render server-paginated pair rows with left/right identity, observation count, Pearson correlation, Spearman correlation, covariance, left-to-right beta, and right-to-left beta where available.
- Default ordering is descending absolute Pearson correlation, then stable left-id/right-id tie-breakers.
- Require a complete, non-empty, non-stale univariate-filter selection.
- Do not transfer the complete pair dataset to the browser and do not calculate correlations in React.

Acceptance:

- Pair count equals `n * (n - 1) / 2` for `n` unique selected listings.
- Same-listing pairs and duplicate reversed pairs never appear.
- Over-limit plans return a clear non-runnable result and create no run or pair artifacts.
- Refreshing a running page reconnects to the existing run.
- Identical run requests reuse the existing running or completed run.
- Result pagination and ordering are stable across repeated requests.
- Tests cover zero, one, two, normal, partially failed, and over-limit selections; source-selection isolation; pair uniqueness; deterministic ordering; and refresh recovery.

Security: Plans, runs, and pair results are scoped to the authenticated user's selected membership and allowed observations.

Determinism: Pair construction, alignment rules, metric versions, ordering, and artifact identity are explicit and versioned.

Idempotency: Identical source selection and algorithm inputs resolve to one logical run and artifact set.

### PR115. Sequential Navigation, Final Legacy Deletion, And End-To-End Gate

Branch: `refactor/four-page-ui-completion-gate`.

Git status: not started. PR: TBD.

Priority: P1 cutover completion.

Depends on: PR114.

Scope:

- Make `apps/web/src/routes.tsx` the only production route registry and keep exactly the four canonical routes.
- Drive navigation status from `GET /api/workflow`. Locked pages remain visible but non-navigable and explain their prerequisite.
- Preserve normal browser refresh, back, forward, and direct-link behavior without adding a global frontend store.
- Delete all unused page components, shell experiments, fixture selectors, catalogues, compatibility adapters, synthetic compute endpoints, obsolete project/dashboard/settings/account/report/portfolio/diversification routes, and stale UI specifications.
- Delete unused `AuthenticatedShell`, old aggregate-only endpoints, old HTML-rendering helpers, duplicate route lists, and any tests whose only purpose is to preserve removed files.
- Add a repository gate that fails when removed route ids, compatibility renderer names, direct page-level `fetch(` calls, the retired metadata-fetch name, or production fixture selectors reappear.
- Update `README.md`, `ARCHITECTURE.md`, `CONTRACTS.md`, `docs/ui/README.md`, `docs/ui/page-development.md`, and the four page specifications to describe only the final implementation.
- Add one Playwright workflow test that completes metadata refresh, metadata filtering, quote loading, univariate statistics, univariate filtering, and bivariate statistics using deterministic mocked provider responses.

Acceptance:

- The production route registry contains exactly four entries in the required order.
- No production file or documentation describes the superseded eight-stage UI as current.
- No placeholder-only production page remains.
- No legacy renderer, compatibility route, duplicate navigation registry, component catalogue, fixture-selection route, or browser-owned financial/statistical computation remains.
- Direct links to locked pages render a prerequisite message without starting work.
- A completed deterministic synthetic workflow survives browser refresh at every stage.
- An upstream change marks all required downstream stages stale and blocks execution until recomputed.
- `npm ci`, TypeScript checking, Vite build, Node syntax checking, Ruff, Pyright, import-linter, the full Python test suite, Playwright, and the repository `pr-quality` gate all pass.
- A repository-wide search for forbidden legacy identifiers returns no tracked production or documentation matches.

Security: The final browser bundle contains no provider secret, authorization rule, raw credential, unrestricted dataset path, or cross-user identifier.

Determinism: The same mocked provider responses and user inputs produce the same workflow ids, page states, progress sequence, selections, and result ordering.

Idempotency: Replaying the complete synthetic workflow creates no duplicate credentials, metadata revisions, selections, quote runs, statistical runs, or artifacts.
"""


def main() -> None:
    original = BACKLOG.read_text(encoding="utf-8")

    completed_history = section(original, "## Completed PR History", "## Current Architectural Decision")
    architecture = section(
        original,
        "## Current Architectural Decision",
        "## Hosted Multi-Tenant Portfell PR Stack",
    )
    hosted = section(
        original,
        "## Hosted Multi-Tenant Portfell PR Stack",
        "## Portfell Research Funnel UI PR Stack",
    )
    old_ui = section(
        original,
        "## Portfell Research Funnel UI PR Stack",
        "## Series Completion Gate",
    )

    hosted_intro, hosted_blocks = split_pr_blocks(hosted)
    active_hosted = [block for block in hosted_blocks if not is_finished(block)]
    finished_hosted = [block for block in hosted_blocks if is_finished(block)]

    policy = """## Backlog Policy

This file is ordered by execution relevance:

1. active, not-yet-finished PR-sized work;
2. current architectural constraints and completion gates;
3. completed and superseded history at the bottom.

Every active item must contain `Branch`, `Git status`, `PR`, `Priority`, `Depends on`, `Scope`, `Acceptance`, `Security`, `Determinism`, and `Idempotency`. A PR is atomic only when it can merge independently with all repository gates green. A PR is complete only when its acceptance criteria are machine-verifiable and no assigned scope is deferred silently.

Completed entries are never deleted. Superseded plans are moved to the historical section and explicitly marked non-active. Backlog identifiers are never reused.
"""

    active_hosted_section = hosted_intro.replace(
        "## Hosted Multi-Tenant Portfell PR Stack",
        "## Active Hosted Multi-Tenant Portfell PR Stack",
        1,
    )
    if active_hosted:
        active_hosted_section += "\n\n" + "\n\n".join(active_hosted)
    else:
        active_hosted_section += "\n\nNo hosted multi-tenant PR is currently active."

    completion_gate = """## Series Completion Gate

The four-page UI series is complete only after PR110 through PR115 are merged and all of the following are true:

- exactly four production pages exist in the required order;
- every page invokes a real backend workflow and has locked, ready, running, complete, failed, and stale behavior where applicable;
- quote and bivariate progress are server-reported rather than simulated in the browser;
- every run and selection is scoped to immutable authenticated-user inputs;
- repeated identical commands reuse existing logical state;
- upstream changes invalidate downstream state deterministically;
- no placeholder page, retired route, compatibility renderer, duplicate registry, synthetic compute endpoint, or legacy documentation remains;
- all Python, TypeScript, build, browser, security, and repository gates pass.

Hosted deployment remains subject to the independent security, licensing, privacy, backup, credential, and readiness requirements in the active hosted PR stack.
"""

    update_rules = """## Update Rules

- Put new active PR entries above architecture and history sections.
- Move an entry to completed history immediately after merge or explicit implementation without a dedicated PR.
- Record the final GitHub PR URL and merge status.
- Update `Last reviewed` whenever active ordering, dependencies, status, or acceptance criteria change.
- Never describe a superseded UI plan as current architecture.
- Keep implementation, tests, contracts, and documentation in the same PR when they define one behavior.
"""

    completed_details = "## Completed And Superseded Detailed Records\n\n"
    if finished_hosted:
        completed_details += "### Completed Hosted Stack Records\n\n" + "\n\n".join(finished_hosted)
    else:
        completed_details += "No additional completed hosted records were classified from the previous active stack."
    completed_details += (
        "\n\n### Superseded Research Funnel UI Stack\n\n"
        "Historical only. The following plan is superseded by PR110 through PR115 and must not be implemented as active scope.\n\n"
        + old_ui
    )

    toc = """## Table Of Contents

- [Backlog Policy](#backlog-policy)
- [Active Four-Page Portfell UI PR Stack](#active-four-page-portfell-ui-pr-stack)
- [Active Hosted Multi-Tenant Portfell PR Stack](#active-hosted-multi-tenant-portfell-pr-stack)
- [Current Architectural Decision](#current-architectural-decision)
- [Series Completion Gate](#series-completion-gate)
- [Update Rules](#update-rules)
- [Completed PR History](#completed-pr-history)
- [Completed And Superseded Detailed Records](#completed-and-superseded-detailed-records)
"""

    rewritten = "\n\n".join(
        part.strip()
        for part in (
            "# Backlog\n\nLast reviewed: 2026-08-04",
            toc,
            policy,
            MINIMAL_UI_STACK,
            active_hosted_section,
            architecture,
            completion_gate,
            update_rules,
            completed_history,
            completed_details,
        )
    )
    BACKLOG.write_text(rewritten.rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
