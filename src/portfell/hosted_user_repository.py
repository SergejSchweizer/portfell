"""PostgreSQL repository for hosted tenant user lifecycle records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from portfell.hosted_catalog import set_authenticated_user_sql


class HostedUserError(ValueError):
    """Raised when a hosted user projection violates its persistence contract."""


@dataclass(frozen=True)
class HostedUser:
    """Tenant user lifecycle record without authentication or credential material."""

    user_id: str
    status: str


class HostedUserCursor(Protocol):
    """Minimal result boundary for hosted user commands."""

    def fetchone(self) -> tuple[object, ...] | None: ...


class HostedUserConnection(Protocol):
    """Parameterized connection boundary for hosted user lifecycle commands."""

    def execute(
        self, sql: str, parameters: tuple[object, ...] = ()
    ) -> HostedUserCursor: ...


class PostgresHostedUserRepository:
    """Persist active users and soft-delete them through user-scoped RLS commands."""

    def __init__(self, connection: HostedUserConnection) -> None:
        self._connection = connection

    def create(self, user_id: str) -> HostedUser:
        """Create or return one active tenant user by stable user id."""

        self._bind_user(user_id)
        self._connection.execute(
            """
insert into portfell_app.users (user_id, status)
values (%s::uuid, 'active')
on conflict (user_id) do nothing
""",
            (user_id,),
        )
        user = self.get(user_id)
        if user is None:
            raise HostedUserError("hosted_user_not_found")
        return user

    def get(self, user_id: str) -> HostedUser | None:
        """Read one tenant user after binding the transaction-local RLS identity."""

        self._bind_user(user_id)
        row = self._connection.execute(
            """
select user_id::text, status
from portfell_app.users
where user_id = %s::uuid
""",
            (user_id,),
        ).fetchone()
        return None if row is None else _hosted_user(row)

    def soft_delete(self, user_id: str) -> None:
        """Mark an owned active or disabled tenant user deleted exactly once."""

        self._bind_user(user_id)
        self._connection.execute(
            """
update portfell_app.users
set status = 'deleted', deleted_at = now(), updated_at = now()
where user_id = %s::uuid and status <> 'deleted'
""",
            (user_id,),
        )

    def _bind_user(self, user_id: str) -> None:
        self._connection.execute(*set_authenticated_user_sql(user_id))


def _hosted_user(row: tuple[object, ...]) -> HostedUser:
    if len(row) != 2 or any(not isinstance(value, str) or not value for value in row):
        raise HostedUserError("hosted_user_projection_invalid")
    user_id, status = (str(value) for value in row)
    if status not in {"active", "disabled", "deleted"}:
        raise HostedUserError("hosted_user_projection_invalid")
    return HostedUser(user_id, status)