"""Immutable row-addressable analytical-artifact items."""

from portfell.app_state.migrations.v001_initial import AppStateMigration

_ANALYSIS_ARTIFACT_ITEMS_SQL = """
create table if not exists portfell.analysis_artifact_items (
    artifact_id text not null references portfell.analysis_artifacts(artifact_id)
        on delete restrict,
    ordinal bigint not null check (ordinal >= 0),
    item_key text check (item_key is null or btrim(item_key) <> ''),
    document jsonb not null check (jsonb_typeof(document) = 'object'),
    primary key (artifact_id, ordinal)
);

create index if not exists analysis_artifact_items_page_idx
    on portfell.analysis_artifact_items (artifact_id, ordinal);
create index if not exists analysis_artifact_items_key_idx
    on portfell.analysis_artifact_items (artifact_id, item_key)
    where item_key is not null;

create or replace function portfell.enforce_analysis_artifact_item_immutable()
returns trigger
language plpgsql
as $$
begin
    raise exception 'analysis_artifact_item_immutable';
end;
$$;

create trigger analysis_artifact_items_immutable
    before update or delete on portfell.analysis_artifact_items
    for each row execute function portfell.enforce_analysis_artifact_item_immutable();
""".strip()

_ANALYSIS_ARTIFACT_ITEMS_DOWN_SQL = """
drop table if exists portfell.analysis_artifact_items;
drop function if exists portfell.enforce_analysis_artifact_item_immutable();
""".strip()

MIGRATION_V003 = AppStateMigration(
    version=3,
    name="row_addressable_analysis_artifact_items_v3",
    sql=_ANALYSIS_ARTIFACT_ITEMS_SQL,
    destructive_down_sql=_ANALYSIS_ARTIFACT_ITEMS_DOWN_SQL,
)
