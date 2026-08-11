"""D018 durable research-run and selection lifecycle schema."""

# ruff: noqa: E501


RESEARCH_LIFECYCLE_SCHEMA_SQL = """
create table if not exists portfell_app.research_runs (
    research_run_id text primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    run_kind text not null check (run_kind in ('univariate', 'bivariate')),
    source_id text not null,
    status text not null check (status in ('running', 'complete', 'failed')),
    total bigint not null check (total >= 0),
    completed bigint not null check (completed >= 0 and completed <= total),
    failed bigint not null default 0 check (failed >= 0 and failed <= total),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, run_kind, research_run_id)
);
create table if not exists portfell_app.research_run_rows (
    research_run_id text not null references portfell_app.research_runs(research_run_id) on delete cascade,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    ordinal integer not null check (ordinal >= 0),
    row_data jsonb not null,
    primary key (research_run_id, ordinal)
);
create table if not exists portfell_app.univariate_selections (
    selection_id text primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    source_run_id text not null references portfell_app.research_runs(research_run_id) on delete cascade,
    member_ids jsonb not null,
    predicates jsonb not null,
    input_count bigint not null check (input_count >= 0),
    created_at timestamptz not null default now()
);
create table if not exists portfell_app.univariate_selection_rows (
    selection_id text not null references portfell_app.univariate_selections(selection_id) on delete cascade,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    ordinal integer not null check (ordinal >= 0),
    row_data jsonb not null,
    primary key (selection_id, ordinal)
);
create table if not exists portfell_app.research_run_quote_bindings (
    research_run_id text primary key references portfell_app.research_runs(research_run_id) on delete cascade,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    quote_run_id uuid not null references portfell_app.download_runs(download_run_id)
);
create table if not exists portfell_app.current_univariate_selection_preferences (
    user_id uuid primary key references portfell_app.users(user_id) on delete cascade,
    selection_id text not null references portfell_app.univariate_selections(selection_id) on delete cascade,
    updated_at timestamptz not null default now()
);
alter table portfell_app.research_runs enable row level security;
alter table portfell_app.research_runs force row level security;
alter table portfell_app.univariate_selections enable row level security;
alter table portfell_app.univariate_selections force row level security;
alter table portfell_app.current_univariate_selection_preferences enable row level security;
alter table portfell_app.current_univariate_selection_preferences force row level security;
alter table portfell_app.research_run_rows enable row level security;
alter table portfell_app.research_run_rows force row level security;
alter table portfell_app.univariate_selection_rows enable row level security;
alter table portfell_app.univariate_selection_rows force row level security;
alter table portfell_app.research_run_quote_bindings enable row level security;
alter table portfell_app.research_run_quote_bindings force row level security;
do $$
declare table_name text;
begin
    foreach table_name in array array[
        'research_runs', 'research_run_rows', 'univariate_selections',
        'univariate_selection_rows', 'research_run_quote_bindings',
        'current_univariate_selection_preferences'
    ] loop
        execute format('drop policy if exists research_user_isolation on portfell_app.%I', table_name);
        execute format(
            'create policy research_user_isolation on portfell_app.%I using (user_id = nullif(current_setting(''portfell.current_user_id'', true), '''')::uuid) with check (user_id = nullif(current_setting(''portfell.current_user_id'', true), '''')::uuid)',
            table_name
        );
    end loop;
end $$;
grant select, insert, update on portfell_app.research_runs,
    portfell_app.research_run_rows,
    portfell_app.univariate_selections,
    portfell_app.univariate_selection_rows,
    portfell_app.research_run_quote_bindings,
    portfell_app.current_univariate_selection_preferences to portfell_app;
"""
