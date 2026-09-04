"""Least-privilege login roles for the modular deployment."""

from portfell.app_state.migrations.v001_initial import AppStateMigration

_MODULE_ROLES_SQL = """
do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'portfell_gateway') then
        create role portfell_gateway login;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'portfell_metadata') then
        create role portfell_metadata login;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'portfell_univariate') then
        create role portfell_univariate login;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'portfell_bivariate') then
        create role portfell_bivariate login;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'portfell_multivariate') then
        create role portfell_multivariate login;
    end if;
end $$;

grant connect on database portfell_dash to portfell_gateway, portfell_metadata,
    portfell_univariate, portfell_bivariate, portfell_multivariate;
grant usage on schema workflow to portfell_gateway;
grant select, insert, update on workflow.stage_commands to portfell_gateway;
grant usage on schema metadata to portfell_metadata;
grant select, insert on metadata.universes to portfell_metadata;
grant usage on schema univariate to portfell_univariate;
grant select, insert on univariate.runs, univariate.selections to portfell_univariate;
grant usage on schema metadata to portfell_univariate;
grant select on metadata.universes to portfell_univariate;
grant usage on schema bivariate to portfell_bivariate;
grant select, insert on bivariate.runs to portfell_bivariate;
grant usage on schema univariate to portfell_bivariate;
grant select on univariate.selections to portfell_bivariate;
grant usage on schema multivariate to portfell_multivariate;
grant select, insert on multivariate.runs to portfell_multivariate;
grant usage on schema bivariate to portfell_multivariate;
grant select on bivariate.runs to portfell_multivariate;
""".strip()

MIGRATION_V006 = AppStateMigration(
    version=6,
    name="module_least_privilege_roles_v6",
    sql=_MODULE_ROLES_SQL,
    destructive_down_sql="""
    revoke all on schema workflow, metadata, univariate, bivariate, multivariate
        from portfell_gateway, portfell_metadata, portfell_univariate,
        portfell_bivariate, portfell_multivariate;
    """.strip(),
)
