# Current-Code Project Isolation Addendum

Status: active normative addendum to `docs/backlog/current-code-correctness-amendment.md` and the PR269/PR273/PR275/PR276 work orders. It is registered by the active base specification `docs/backlog/plotly-dash-multivariate-optimizer-ui.md` and is therefore part of the PR264-PR276 implementation authority.

Review basis: current `main` at `69d76a108257a9d07dd8e22a918ae789942afc07`.

## CCR-13 — Current Univariate selection preference is user-global, not project-scoped — P0 isolation

Current PostgreSQL behavior stores the current Univariate selection in `current_univariate_selection_preferences` with conflict key `user_id` only:

```text
insert (user_id, selection_id)
on conflict (user_id) do update ...
```

`UnivariateResearchService.complete()` and `apply_selection()` both call `set_current_univariate_selection(user_id, selection_id)` without a project ID. `workflow_state(project_id=...)` then calls `_current_selection_for_run(user_id, univariate_run_id)`, which reads that one user-global preference and only afterwards checks whether the chosen selection belongs to the requested run.

With two projects for one user, selecting or recomputing Project B can therefore replace the preference previously used by Project A. Project A's subsequent workflow projection can lose its current Univariate selection/Bivariate chain even though its persisted selection still exists. This violates the active two-project isolation contract and would also make the planned weekly multi-project cycle order-dependent.

This is not a browser-only problem; it is a durable control-plane keying defect.

## Mandatory PR269 acceptance additions

Add these rows to PR269's single `Tasks / Acceptance` checklist:

- [ ] Freeze current research-selection identity as project-scoped. A current Univariate selection preference is identified by at least `(user_id, project_id)` and references a selection whose source run is mapped to the same project. User-global current-selection authority is forbidden.
- [ ] Freeze service/repository signatures so setting or reading the current Univariate selection requires explicit project identity (or an already-authorized project/run binding from which project identity is deterministically resolved). A caller cannot set Project A's current preference to a selection owned by Project B.
- [ ] Two-project contract fixture creates independent current selections for A and B, changes A twice, and proves B's selection/run chain and revision remain byte-identical.

## Mandatory PR273 acceptance additions

Add these rows to PR273's single `Tasks / Acceptance` checklist:

- [ ] Migrate/persist `current_univariate_selection_preferences` under project-scoped authority. The database uniqueness/key contract prevents one project's selection update from replacing another project's preference for the same user.
- [ ] Migration/backfill is fail-closed and deterministic: infer project only from the persisted source-run/project mapping; ambiguous or orphaned legacy preference is not silently assigned to an arbitrary project and receives explicit repair evidence.
- [ ] Repository `workflow_state(user_id, project_id, ...)` resolves the current selection directly inside the requested project scope; it never consults one user-global preference first.
- [ ] PostgreSQL integration test with two projects proves concurrent/reordered selection writes cannot cross-contaminate current selection, Bivariate run identity, or Multivariate preference.

## Mandatory PR275 acceptance additions

Add these rows to PR275's single `Tasks / Acceptance` checklist:

- [ ] Final Dash/FastAPI two-project E2E changes Univariate filters/selections repeatedly in Project A and proves Project B retains its own current selection, Bivariate result, Multivariate result, objective, and navigation state across app restart.
- [ ] Architecture/schema gate rejects any final production current-Univariate-selection table/repository API whose uniqueness is user-only rather than project-scoped.

## Mandatory PR276 acceptance additions

Add these rows to PR276's single `Tasks / Acceptance` checklist:

- [ ] Weekly project iteration reads/writes each project's own persisted Univariate selection preference. Processing order A->B versus B->A produces identical per-project Uni/Bi/Multivariate run identities and terminal results.
- [ ] Two-project weekly fixture gives A and B different Univariate predicates. After a complete cycle and restart, both projects retain their own selection settings/preferences and downstream Bivariate/Multivariate chains; neither project inherits the other project's selection.

## Project-isolation completion gate

The full PR264-PR276 series is not complete until one PostgreSQL-backed deterministic fixture proves:

```text
same user
  |- Project A -> current Univariate selection A -> Bivariate A -> Multivariate A
  `- Project B -> current Univariate selection B -> Bivariate B -> Multivariate B
```

Changing, recomputing, restarting, or weekly-refreshing either branch must leave the other branch unchanged. No user-global `current_univariate_selection` authority may remain in production.