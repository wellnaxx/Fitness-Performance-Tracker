"""PostgreSQL unit of work with explicit commit and rollback by default."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from psycopg import Error

from core.errors.database import DatabaseError
from data.connection import get_connection
from repositories.set_entry_unit_of_work_repository import SetEntryUnitOfWorkRepository
from repositories.user_goals_unit_of_work_repository import UserGoalsUnitOfWorkRepository
from repositories.workout_exercise_unit_of_work_repository import WorkoutExerciseUnitOfWorkRepository

if TYPE_CHECKING:
    from types import TracebackType

    from psycopg import Connection, Cursor

    from data.executor import Row
    from ports.unit_of_work import (
        UnitOfWorkSetEntryRepositoryPort,
        UnitOfWorkUserGoalsRepositoryPort,
        UnitOfWorkWorkoutExerciseRepositoryPort,
    )


class PostgresUnitOfWork:
    """Own one connection and cursor for all repositories in a service operation."""

    def __init__(self) -> None:
        """Initialize transaction state and its logger without opening a connection."""
        self.logger = logging.getLogger(__name__)
        self._conn: Connection[Row] | None = None
        self._cursor: Cursor[Row] | None = None
        self._goals: UnitOfWorkUserGoalsRepositoryPort | None = None
        self._set_entry: UnitOfWorkSetEntryRepositoryPort | None = None
        self._workout_exercise: UnitOfWorkWorkoutExerciseRepositoryPort | None = None
        self._committed = False

    @property
    def goals(self) -> UnitOfWorkUserGoalsRepositoryPort:
        if self._goals is None:
            raise DatabaseError.no_active_transaction()
        return self._goals

    @property
    def set_entry(self) -> UnitOfWorkSetEntryRepositoryPort:
        """Return the set repository while active; reject access outside the context."""
        if self._set_entry is None:
            raise DatabaseError.no_active_transaction()
        return self._set_entry

    @property
    def workout_exercise(self) -> UnitOfWorkWorkoutExerciseRepositoryPort:
        """Return the workout-exercise repository only while the transaction is active."""
        if self._workout_exercise is None:
            raise DatabaseError.no_active_transaction()
        return self._workout_exercise

    def __enter__(self) -> PostgresUnitOfWork:
        """Open one shared cursor for repositories; clean up partial setup failures."""
        if self._conn is not None:
            raise DatabaseError.transaction_already_active()

        conn: Connection[Row] | None = None
        cursor: Cursor[Row] | None = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            goals = UserGoalsUnitOfWorkRepository(cursor)
            set_entry = SetEntryUnitOfWorkRepository(cursor)
            workout_exercise = WorkoutExerciseUnitOfWorkRepository(cursor)
        except Exception as exc:
            self._close_resources(cursor, conn)
            if isinstance(exc, DatabaseError):
                raise
            self.logger.exception("Failed to open database unit of work")
            raise DatabaseError.transaction_failed(exc) from exc

        self._conn = conn
        self._cursor = cursor
        self._goals = goals
        self._set_entry = set_entry
        self._workout_exercise = workout_exercise
        self._committed = False
        self.logger.debug("Database unit of work opened")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Roll back uncommitted work, clear repositories, and close database resources.

        Preserve application exceptions if rollback also fails. Translate driver
        errors into DatabaseError after cleanup; never suppress the body error.
        """
        rollback_error: Exception | None = None
        try:
            if not self._committed:
                try:
                    self.rollback()
                except Exception as error:
                    rollback_error = error
                    self.logger.exception("Failed to roll back database unit of work")
        finally:
            self._close_resources(self._cursor, self._conn)
            self._cursor = None
            self._conn = None
            self._goals = None
            self._set_entry = None
            self._workout_exercise = None

        if isinstance(exc, Error):
            self.logger.error("Database transaction failed", exc_info=(type(exc), exc, tb))
            raise DatabaseError.transaction_failed(exc) from exc
        if exc_type is None and rollback_error is not None:
            raise rollback_error

    def commit(self) -> None:
        """Persist the operation only after all writes and result mapping succeed."""
        if self._conn is None:
            raise DatabaseError.no_active_transaction()
        try:
            self._conn.commit()
        except DatabaseError:
            raise
        except Exception as exc:
            self.logger.exception("Failed to commit database unit of work")
            raise DatabaseError.transaction_failed(exc) from exc
        self._committed = True
        self.logger.debug("Database unit of work committed")

    def rollback(self) -> None:
        if self._conn is None:
            raise DatabaseError.no_active_transaction()
        try:
            self._conn.rollback()
        except DatabaseError:
            raise
        except Exception as exc:
            self.logger.exception("Failed to roll back database transaction")
            raise DatabaseError.transaction_failed(exc) from exc
        self._committed = False
        self.logger.debug("Database unit of work rolled back")

    def _close_resources(self, cursor: Cursor[Row] | None, conn: Connection[Row] | None) -> None:
        """Close all acquired resources while preserving the original transaction error.

        Args:
            cursor: Acquired cursor, or None if setup did not reach cursor creation.
            conn: Acquired connection, or None if opening the connection failed.

        Returns:
            None; cleanup failures are logged without hiding the original failure.
        """
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                self.logger.exception("Failed to close unit-of-work cursor")
        if conn is not None:
            try:
                conn.close()
            except Exception:
                self.logger.exception("Failed to close unit-of-work connection")
