"""Schema migration for encrypted provider credential wrapping metadata."""

PROVIDER_CREDENTIAL_WRAP_NONCE_SCHEMA_SQL = """
alter table portfell_app.provider_credentials
    add column if not exists wrap_nonce bytea;

do $$
begin
    if exists (
        select 1
        from portfell_app.provider_credentials
        where wrap_nonce is null
    ) then
        raise exception 'provider credential rows require a wrap nonce migration';
    end if;
end $$;

alter table portfell_app.provider_credentials
    alter column wrap_nonce set not null;

alter table portfell_app.provider_credentials
    drop constraint if exists provider_credentials_user_id_provider_status_key;

create unique index if not exists provider_credentials_one_active_user_provider_idx
    on portfell_app.provider_credentials (user_id, provider)
    where status = 'active';
"""
