"""Workout-exercise ordering and reference locks on the unit of work's cursor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from data.executor import TransactionExecutor
from data.queries import QUERIES
from repositories.workout_exercise_repository import WorkoutExerciseRepository

if TYPE_CHECKING:
    from psycopg import Cursor

    from data.executor import Row


class WorkoutExerciseUnitOfWorkRepository(WorkoutExerciseRepository):
    """Share one cursor for authorization, validation, shifts, and write readbacks."""

    def __init__(self, cursor: Cursor[Row]) -> None:
        """Bind inherited queries without opening a connection or committing.

        Args:
            cursor: Cursor owned by the active unit of work.
        """
        super().__init__(TransactionExecutor(cursor))

    def lock_for_workout(self, user_id: int, workout_id: int) -> bool:
        """Lock an owned workout, including one without exercises.

        Args:
            user_id: Authenticated owner ID.
            workout_id: Requested parent workout ID.

        Returns:
            True if the owned parent is locked until commit or rollback; False
            for missing, global, or foreign-owned parents.

        Raises:
            DatabaseError: If the lock query fails.
        """
        return (
            self._executor.fetch_one(QUERIES.workout_exercises.lock_for_workout, (workout_id, user_id))
            is not None
        )

    def lock_visible_exercise(self, user_id: int, exercise_id: int) -> bool:
        """Prevent deletion or visibility changes to the referenced exercise.

        Args:
            user_id: Authenticated owner ID.
            exercise_id: Requested global or user-owned catalog exercise ID.

        Returns:
            True if a visible exercise is locked for shared access until commit
            or rollback; False if missing or foreign-owned.

        Raises:
            DatabaseError: If the lock query fails.
        """
        return (
            self._executor.fetch_one(QUERIES.workout_exercises.lock_visible_exercise, (exercise_id, user_id))
            is not None
        )
