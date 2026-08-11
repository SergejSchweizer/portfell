"""Forward-only PostgreSQL repair for project-membership immutability."""

from __future__ import annotations

PROJECT_MEMBERSHIP_TRIGGER_REPAIR_SQL = """
create or replace function portfell_app.reject_project_membership_mutation()
returns trigger
language plpgsql
as $$
begin
    if tg_table_name = 'project_selection_versions' then
        if tg_op = 'UPDATE'
            and old.membership_sealed_at is null
            and new.membership_sealed_at is not null then
            return new;
        end if;
        raise exception 'project_membership_immutable';
    end if;
    if tg_table_name = 'project_selection_members' then
        if tg_op = 'INSERT'
            and not exists (
                select 1
                from portfell_app.project_selection_versions
                where selection_version_id = new.selection_version_id
                  and membership_sealed_at is not null
            ) then
            return new;
        end if;
        raise exception 'project_membership_immutable';
    end if;
    raise exception 'project_membership_immutable';
end;
$$;
"""
