"""Reuse goal SQL and mapping through the unit of work's shared cursor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from data.executor import TransactionExecutor
from data.queries import QUERIES
from repositories.user_goals_repository import UserGoalsRepository

if TYPE_CHECKING:
    from psycopg import Cursor

    from data.executor import Row


class UserGoalsUnitOfWorkRepository(UserGoalsRepository):
    """All inherited reads and writes use one cursor and never commit."""

    def __init__(self, cursor: Cursor[Row]) -> None:
        """Bind inherited goal operations to the active transaction's cursor.

        Args:
            cursor: Cursor owned by the active transaction.
        """
        super().__init__(TransactionExecutor(cursor))

    def lock_for_user(self, user_id: int) -> bool:
        """Lock the owner, including when they have no goals yet.

        Args:
            user_id: Owner user ID to lock.

        Returns:
            True if the owner exists and is locked until transaction completion;
            False if the owner does not exist.

        Raises:
            DatabaseError: If the database operation fails.
        """
        return self._executor.fetch_one(QUERIES.user_goals.lock_for_user, (user_id,)) is not None
