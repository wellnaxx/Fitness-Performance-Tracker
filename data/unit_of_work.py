"""PostgreSQL unit of work with explicit commit and rollback by default."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from psycopg import Error

from core.errors.database import DatabaseError
from data.connection import get_connection
from repositories.user_goals_unit_of_work_repository import UserGoalsUnitOfWorkRepository

if TYPE_CHECKING:
    from types import TracebackType

    from psycopg import Connection, Cursor

    from data.executor import Row
    from ports.unit_of_work import UnitOfWorkUserGoalsRepositoryPort

logger = logging.getLogger(__name__)


class PostgresUnitOfWork:
    """Own one connection and cursor for all repositories in a service operation."""

    def __init__(self) -> None:
        self._conn: Connection[Row] | None = None
        self._cursor: Cursor[Row] | None = None
        self._goals: UnitOfWorkUserGoalsRepositoryPort | None = None
        self._committed = False

    @property
    def goals(self) -> UnitOfWorkUserGoalsRepositoryPort:
        if self._goals is None:
            raise DatabaseError.no_active_transaction()
        return self._goals

    def __enter__(self) -> PostgresUnitOfWork:
        if self._conn is not None:
            raise DatabaseError.transaction_already_active()

        conn: Connection[Row] | None = None
        cursor: Cursor[Row] | None = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            goals = UserGoalsUnitOfWorkRepository(cursor)
        except Exception as exc:
            self._close_resources(cursor, conn)
            if isinstance(exc, DatabaseError):
                raise
            logger.exception("Failed to open database unit of work")
            raise DatabaseError.transaction_failed(exc) from exc

        self._conn = conn
        self._cursor = cursor
        self._goals = goals
        self._committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        rollback_error: Exception | None = None
        try:
            if not self._committed:
                try:
                    self.rollback()
                except Exception as error:
                    rollback_error = error
                    logger.exception("Failed to roll back database unit of work")
        finally:
            self._close_resources(self._cursor, self._conn)
            self._cursor = None
            self._conn = None
            self._goals = None

        if isinstance(exc, Error):
            logger.error("Database transaction failed", exc_info=(type(exc), exc, tb))
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
            logger.exception("Failed to commit database unit of work")
            raise DatabaseError.transaction_failed(exc) from exc
        self._committed = True

    def rollback(self) -> None:
        if self._conn is None:
            raise DatabaseError.no_active_transaction()
        try:
            self._conn.rollback()
        except DatabaseError:
            raise
        except Exception as exc:
            logger.exception("Failed to roll back database transaction")
            raise DatabaseError.transaction_failed(exc) from exc
        self._committed = False

    @staticmethod
    def _close_resources(cursor: Cursor[Row] | None, conn: Connection[Row] | None) -> None:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                logger.exception("Failed to close unit-of-work cursor")
        if conn is not None:
            try:
                conn.close()
            except Exception:
                logger.exception("Failed to close unit-of-work connection")
