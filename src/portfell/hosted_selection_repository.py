"""PostgreSQL repository for immutable project selection membership."""

from __future__ import annotations

import hashlib
from typing import Protocol

from portfell.hosted_catalog import set_authenticated_user_sql
from portfell.hosted_repository_importer import TenantImportError, TenantSelection


class SelectionCursor(Protocol):
    """Minimal PostgreSQL result protocol for selection membership queries."""

    def fetchall(self) -> list[tuple[object, ...]]: ...


class SelectionConnection(Protocol):
    """Parameterized connection boundary for an owned selection command."""

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> SelectionCursor: ...


class SelectionRepository(Protocol):
    """User-scoped immutable project selection persistence port."""

    def create(self, selection: TenantSelection) -> TenantSelection: ...

    def for_project(self, *, project_id: str, user_id: str) -> TenantSelection | None: ...

    def by_id(self, *, selection_id: str, user_id: str) -> TenantSelection | None: ...


class InMemorySelectionRepository:
    """Contract test double for immutable user-scoped selection membership."""

    def __init__(self) -> None:
        self._selections: dict[str, TenantSelection] = {}

    def create(self, selection: TenantSelection) -> TenantSelection:
        existing = self.for_project(project_id=selection.project_id, user_id=selection.user_id)
        if existing is not None and existing != selection:
            raise TenantImportError("project_membership_immutable")
        self._selections.setdefault(selection.selection_id, selection)
        return selection

    def for_project(self, *, project_id: str, user_id: str) -> TenantSelection | None:
        return next(
            (
                selection
                for selection in self._selections.values()
                if selection.project_id == project_id and selection.user_id == user_id
            ),
            None,
        )

    def by_id(self, *, selection_id: str, user_id: str) -> TenantSelection | None:
        selection = self._selections.get(selection_id)
        return selection if selection is not None and selection.user_id == user_id else None


class PostgresSelectionRepository:
    """Persist and read one sealed canonical selection membership per project."""

    def __init__(self, connection: SelectionConnection) -> None:
        self._connection = connection

    def create(self, selection: TenantSelection) -> TenantSelection:
        """Create an immutable selection or reject a changed selection for the project."""

        self._bind_user(selection.user_id)
        membership_hash = hashlib.sha256("\n".join(selection.member_ids).encode()).hexdigest()
        self._connection.execute(
            """
insert into portfell_app.project_selection_versions (
    selection_version_id, project_id, user_id, name, membership_hash,
    canonical_listing_policy_version
) values (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'selection-v1')
on conflict (project_id) do nothing
""",
            (
                selection.selection_id,
                selection.project_id,
                selection.user_id,
                selection.name,
                membership_hash,
            ),
        )
        existing = self.for_project(project_id=selection.project_id, user_id=selection.user_id)
        if existing is not None and existing != selection:
            raise TenantImportError("project_membership_immutable")
        if existing is not None:
            return existing
        for member_id in selection.member_ids:
            isin, exchange, code = member_id.split(":")
            self._connection.execute(
                """
insert into portfell_app.project_selection_members (
    selection_version_id, project_id, user_id, isin, provider, exchange, code, canonical_listing_id
) values (%s::uuid, %s::uuid, %s::uuid, %s, 'eodhd', %s, %s, %s)
""",
                (
                    selection.selection_id,
                    selection.project_id,
                    selection.user_id,
                    isin,
                    exchange,
                    code,
                    member_id,
                ),
            )
        self._connection.execute(
            """
update portfell_app.project_selection_versions
set membership_sealed_at = now()
where selection_version_id = %s::uuid and membership_sealed_at is null
""",
            (selection.selection_id,),
        )
        return selection

    def for_project(self, *, project_id: str, user_id: str) -> TenantSelection | None:
        """Read an owned sealed selection with canonical member ordering."""

        self._bind_user(user_id)
        rows = self._connection.execute(
            """
select version.selection_version_id::text, version.project_id::text, version.user_id::text,
       version.name, member.isin, member.exchange, member.code
from portfell_app.project_selection_versions as version
join portfell_app.project_selection_members as member
  on member.selection_version_id = version.selection_version_id
where version.project_id = %s::uuid and version.membership_sealed_at is not null
order by member.isin, member.exchange, member.code
""",
            (project_id,),
        ).fetchall()
        if not rows:
            return None
        first = rows[0]
        if len(first) != 7 or any(not isinstance(value, str) or not value for value in first):
            raise TenantImportError("selection_projection_invalid")
        selection_id, stored_project_id, stored_user_id, name, _, _, _ = first
        members = tuple(f"{row[4]}:{row[5]}:{row[6]}" for row in rows)
        return TenantSelection(
            str(selection_id),
            str(stored_project_id),
            str(stored_user_id),
            str(name),
            members,
        )

    def by_id(self, *, selection_id: str, user_id: str) -> TenantSelection | None:
        self._bind_user(user_id)
        rows = self._connection.execute(
            """
select version.selection_version_id::text, version.project_id::text, version.user_id::text,
       version.name, member.isin, member.exchange, member.code
from portfell_app.project_selection_versions as version
join portfell_app.project_selection_members as member
  on member.selection_version_id = version.selection_version_id
where version.selection_version_id = %s::uuid and version.membership_sealed_at is not null
order by member.isin, member.exchange, member.code
""",
            (selection_id,),
        ).fetchall()
        return _selection_from_rows(rows)

    def _bind_user(self, user_id: str) -> None:
        self._connection.execute(*set_authenticated_user_sql(user_id))


def _selection_from_rows(rows: list[tuple[object, ...]]) -> TenantSelection | None:
    if not rows:
        return None
    first = rows[0]
    if len(first) != 7 or any(not isinstance(value, str) or not value for value in first):
        raise TenantImportError("selection_projection_invalid")
    selection_id, project_id, user_id, name, _, _, _ = first
    return TenantSelection(
        str(selection_id),
        str(project_id),
        str(user_id),
        str(name),
        tuple(f"{row[4]}:{row[5]}:{row[6]}" for row in rows),
    )
