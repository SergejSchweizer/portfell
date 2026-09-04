"""Durable command enqueue, claim and progress operations.

Only stage identifiers and operation metadata cross this boundary. Analytical
rows are deliberately not accepted by the API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from portfell_contracts import JobProgress, Stage


class Cursor(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...


class Connection(Protocol):
    def execute(self, query: str, params: tuple[object, ...] | None = None) -> Cursor: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class WorkflowRepositoryError(RuntimeError):
    """Safe workflow persistence failure."""


@dataclass(frozen=True, slots=True)
class WorkflowCommand:
    command_id: str
    stage: Stage
    input_ref: str
    operation: str
    algorithm_version: str
    idempotency_key: str

    def __post_init__(self) -> None:
        if any(
            not value.strip()
            for value in (
                self.command_id,
                self.input_ref,
                self.operation,
                self.algorithm_version,
                self.idempotency_key,
            )
        ):
            raise ValueError("workflow command fields must be non-empty")
        if self.stage is Stage.GATEWAY:
            raise ValueError("gateway cannot own analytical commands")


class WorkflowCommandRepository:
    """Repository with transactional claim and stale-lease recovery."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def enqueue(self, command: WorkflowCommand) -> WorkflowCommand:
        try:
            cursor = self.connection.execute(
                """
                insert into workflow.stage_commands
                    (command_id, stage, input_ref, operation, idempotency_key, algorithm_version)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (idempotency_key) do update
                    set command_id = workflow.stage_commands.command_id
                returning command_id, stage, input_ref, operation, algorithm_version,
                    idempotency_key
                """,
                (
                    command.command_id,
                    command.stage.value,
                    command.input_ref,
                    command.operation,
                    command.idempotency_key,
                    command.algorithm_version,
                ),
            )
            row = cursor.fetchone()
            self.connection.commit()
            if row is None:
                raise WorkflowRepositoryError("workflow_command_not_returned")
            return self._command(row)
        except WorkflowRepositoryError:
            self.connection.rollback()
            raise
        except Exception as error:
            self.connection.rollback()
            raise WorkflowRepositoryError("workflow_command_enqueue_failed") from error

    def claim(self, *, worker_id: str, lease_seconds: int = 300) -> WorkflowCommand | None:
        if not worker_id.strip() or lease_seconds <= 0:
            raise ValueError("worker_id and lease_seconds are required")
        try:
            cursor = self.connection.execute(
                """
                update workflow.stage_commands
                   set status = 'running', claimed_at = now(),
                       lease_expires_at = now() + (%s * interval '1 second'),
                       progress_phase = 'starting'
                 where command_id = (
                    select command_id from workflow.stage_commands
                     where status = 'queued' or (status = 'running' and lease_expires_at < now())
                     order by requested_at
                     for update skip locked limit 1
                 )
                returning command_id, stage, input_ref, operation, algorithm_version,
                    idempotency_key
                """,
                (lease_seconds,),
            )
            row = cursor.fetchone()
            self.connection.commit()
            return self._command(row) if row else None
        except Exception as error:
            self.connection.rollback()
            raise WorkflowRepositoryError("workflow_command_claim_failed") from error

    def update_progress(self, command_id: str, progress: JobProgress) -> None:
        try:
            self.connection.execute(
                """
                update workflow.stage_commands
                   set status = %s, progress_current = %s, progress_total = %s, progress_phase = %s
                 where command_id = %s and status = 'running'
                """,
                (
                    progress.status.value,
                    progress.current,
                    progress.total,
                    progress.phase,
                    command_id,
                ),
            )
            self.connection.commit()
        except Exception as error:
            self.connection.rollback()
            raise WorkflowRepositoryError("workflow_progress_update_failed") from error

    def recover_stale(self) -> int:
        """Return stale running commands to queued without duplicating output."""

        try:
            cursor = self.connection.execute(
                """
                update workflow.stage_commands
                   set status = 'queued', claimed_at = null, lease_expires_at = null,
                       progress_phase = 'recovered'
                 where status = 'running' and lease_expires_at < now()
                returning command_id
                """
            )
            count = 0
            while cursor.fetchone() is not None:
                count += 1
            self.connection.commit()
            return count
        except Exception as error:
            self.connection.rollback()
            raise WorkflowRepositoryError("workflow_stale_recovery_failed") from error

    @staticmethod
    def _command(row: tuple[object, ...]) -> WorkflowCommand:
        try:
            return WorkflowCommand(
                command_id=str(row[0]),
                stage=Stage(str(row[1])),
                input_ref=str(row[2]),
                operation=str(row[3]),
                algorithm_version=str(row[4]),
                idempotency_key=str(row[5]),
            )
        except (IndexError, ValueError) as error:
            raise WorkflowRepositoryError("workflow_command_record_invalid") from error
