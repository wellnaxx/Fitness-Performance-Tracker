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
        super().__init__(TransactionExecutor(cursor))

    def lock_for_user(self, user_id: int) -> bool:
        """Lock the owner, including when they have no goals yet."""
        return self._executor.fetch_one(QUERIES.user_goals.lock_for_user, (user_id,)) is not None
