"""Forward-only storage for immutable Metadata Builder selection criteria."""

METADATA_BUILDER_CRITERIA_SCHEMA_SQL = """
alter table portfell_app.project_selection_versions
    add column if not exists metadata_builder_predicates jsonb not null default '[]'::jsonb;
"""
