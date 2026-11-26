"""Set-entry queries and parent locking bound to the unit of work's cursor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from data.executor import TransactionExecutor
from data.queries import QUERIES
from repositories.set_entry_repository import SetEntryRepository

if TYPE_CHECKING:
    from psycopg import Cursor

    from data.executor import Row


class SetEntryUnitOfWorkRepository(SetEntryRepository):
    """Reuse set-entry SQL and mapping without opening connections or committing."""

    def __init__(self, cursor: Cursor[Row]) -> None:
        """Bind inherited operations to the cursor owned by the active unit of work.

        Args:
            cursor: Cursor owned by the active transaction.
        """
        super().__init__(TransactionExecutor(cursor))

    def lock_for_workout_exercise(self, workout_exercise_id: int) -> bool:
        """Acquire FOR UPDATE on the parent row; return False when it is absent.

        Locking the parent protects ordering even when no child sets exist.
        The lock lasts until the owning transaction commits or rolls back.

        Args:
            workout_exercise_id: Workout exercise ID within the parent workout.

        Returns:
            True if the parent exists and is locked until transaction completion;
            False if the parent does not exist.

        Raises:
            DatabaseError: If the database operation fails.
        """
        return (
            self._executor.fetch_one(QUERIES.set_entries.lock_for_workout_exercise, (workout_exercise_id,))
            is not None
        )
