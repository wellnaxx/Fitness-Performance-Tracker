"""
Workout Exercise Repository

This module handles all database interactions for the WorkoutExercise entity.
It translates between database rows (now dicts) and Pydantic models.
"""

from __future__ import annotations

from typing import Final, TypedDict

from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from schemas.workout_exercises_schema import (
    WorkoutExerciseCreate,
    WorkoutExercisePublic,
    WorkoutExerciseUpdate,
)
from core.errors.repository import WorkoutExerciseRepositoryError, WorkoutExerciseRowError


class WorkoutExerciseRow(TypedDict):
    id: int
    workout_id: int
    exercise_id: int
    order_index: int
    rest_seconds: int | None
    notes: str | None


class WorkoutExerciseRepository:
    """
    Repository for WorkoutExercise database operations.

    Responsibilities:
    - Execute SQL queries related to workout exercises
    - Convert database row dicts to WorkoutExercisePublic models
    - Handle all workout-exercise-related database logic
    """

    _BASE_SELECT: Final[str] = """
        SELECT id, workout_id, exercise_id, order_index, rest_seconds, notes
        FROM workout_exercises
    """

    _WORKOUT_EXERCISE_UPDATE_WHITELIST: Final[set[str]] = {
        "exercise_id",
        "order_index",
        "rest_seconds",
        "notes",
    }

    def create(
        self,
        workout_exercise_data: WorkoutExerciseCreate,
    ) -> WorkoutExercisePublic:
        """
        Create a new workout exercise row.

        Args:
            workout_exercise_data: Workout exercise creation payload.

        Returns:
            The newly created workout exercise.

        Raises:
            WorkoutExerciseRepositoryError: If the inserted row cannot be retrieved afterwards.
        """
        sql = """
            INSERT INTO workout_exercises
            (workout_id, exercise_id, order_index, rest_seconds, notes)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        workout_exercise_id = execute_insert(
            sql,
            (
                workout_exercise_data.workout_id,
                workout_exercise_data.exercise_id,
                workout_exercise_data.order_index,
                workout_exercise_data.rest_seconds,
                workout_exercise_data.notes,
            ),
        )

        workout_exercise = self.get_by_id(workout_exercise_id)
        if workout_exercise is None:
            raise WorkoutExerciseRepositoryError.inserted_missing(workout_exercise_id)
        return workout_exercise

    def get_by_id(self, workout_exercise_id: int) -> WorkoutExercisePublic | None:
        """
        Retrieve a workout exercise by its database ID.

        Args:
            workout_exercise_id: Workout exercise ID.

        Returns:
            The workout exercise if found, otherwise None.
        """
        row = fetch_one(f"{self._BASE_SELECT} WHERE id = %s", (workout_exercise_id,))
        if row is None:
            return None
        return self._row_to_workout_exercise(row)

    def get_by_workout_and_id(
        self,
        workout_id: int,
        workout_exercise_id: int,
    ) -> WorkoutExercisePublic | None:
        """
        Retrieve a workout exercise by ID only if it belongs to the workout.

        Args:
            workout_id: Parent workout ID.
            workout_exercise_id: Workout exercise ID.

        Returns:
            The workout exercise if found, otherwise None.
        """
        row = fetch_one(
            f"{self._BASE_SELECT} WHERE workout_id = %s AND id = %s",
            (workout_id, workout_exercise_id),
        )
        if row is None:
            return None
        return self._row_to_workout_exercise(row)

    def list_by_workout(self, workout_id: int) -> list[WorkoutExercisePublic]:
        """
        List workout exercises for a workout.

        Args:
            workout_id: Parent workout ID.

        Returns:
            Workout exercises ordered by `order_index`.
        """
        rows = fetch_all(
            f"{self._BASE_SELECT} WHERE workout_id = %s ORDER BY order_index ASC, id ASC",
            (workout_id,),
        )
        return [self._row_to_workout_exercise(row) for row in rows]

    def update_in_workout(
        self,
        workout_id: int,
        workout_exercise_id: int,
        update_data: WorkoutExerciseUpdate,
    ) -> WorkoutExercisePublic | None:
        """
        Partially update a workout exercise within a workout.

        Args:
            workout_id: Parent workout ID.
            workout_exercise_id: Workout exercise ID.
            update_data: Partial update payload.

        Returns:
            The updated workout exercise if found, otherwise None.

        Raises:
            WorkoutExerciseRepositoryError: If any provided fields are not allowed to be updated.
        """
        fields = update_data.model_dump(exclude_none=True)
        if not fields:
            return self.get_by_workout_and_id(workout_id, workout_exercise_id)

        unknown = set(fields) - self._WORKOUT_EXERCISE_UPDATE_WHITELIST
        if unknown:
            raise WorkoutExerciseRepositoryError.invalid_update_fields(unknown)

        set_clause = ", ".join(f"{field} = %s" for field in fields)
        sql = f"UPDATE workout_exercises SET {set_clause} WHERE workout_id = %s AND id = %s"
        execute_write(sql, (*fields.values(), workout_id, workout_exercise_id))
        return self.get_by_workout_and_id(workout_id, workout_exercise_id)

    def delete_in_workout(self, workout_id: int, workout_exercise_id: int) -> bool:
        """
        Delete a workout exercise from a workout.

        Args:
            workout_id: Parent workout ID.
            workout_exercise_id: Workout exercise ID.

        Returns:
            True if a row was deleted, otherwise False.
        """
        return (
            execute_write(
                "DELETE FROM workout_exercises WHERE workout_id = %s AND id = %s",
                (workout_id, workout_exercise_id),
            )
            > 0
        )

    def shift_order_indexes(
        self,
        workout_id: int,
        from_index: int,
        delta: int,
    ) -> None:
        """
        Shift order indexes at or after a given position for one workout.

        Args:
            workout_id: Parent workout ID.
            from_index: Inclusive order index to start shifting from.
            delta: Signed amount to add to each matching order index.
        """
        execute_write(
            """
            UPDATE workout_exercises
            SET order_index = order_index + %s
            WHERE workout_id = %s AND order_index >= %s
            """,
            (delta, workout_id, from_index),
        )

    def normalize_order_indexes(self, workout_id: int) -> None:
        """
        Renumber workout exercises sequentially starting at 0 for a workout.

        Args:
            workout_id: Parent workout ID.
        """
        execute_write(
            """
            WITH ordered_exercises AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY order_index ASC, id ASC) - 1 AS new_index
                FROM workout_exercises
                WHERE workout_id = %s
            )
            UPDATE workout_exercises AS we
            SET order_index = ordered_exercises.new_index
            FROM ordered_exercises
            WHERE we.id = ordered_exercises.id
            """,
            (workout_id,),
        )

    def list_by_workout_id(self, workout_id: int) -> list[WorkoutExercisePublic]:
        """Compatibility wrapper for `list_by_workout`."""
        return self.list_by_workout(workout_id)

    def update(
        self,
        workout_exercise_id: int,
        workout_id: int,
        update_data: WorkoutExerciseUpdate,
    ) -> WorkoutExercisePublic | None:
        """Compatibility wrapper for `update_in_workout`."""
        return self.update_in_workout(workout_id, workout_exercise_id, update_data)

    def delete(self, workout_exercise_id: int, workout_id: int) -> bool:
        """Compatibility wrapper for `delete_in_workout`."""
        return self.delete_in_workout(workout_id, workout_exercise_id)

    def shift_order_indices(
        self,
        workout_id: int,
        start_index: int,
        shift_amount: int,
    ) -> None:
        """Compatibility wrapper for `shift_order_indexes`."""
        self.shift_order_indexes(workout_id, start_index, shift_amount)

    def normalize_order_indices(self, workout_id: int) -> None:
        """Compatibility wrapper for `normalize_order_indexes`."""
        self.normalize_order_indexes(workout_id)

    @staticmethod
    def _parse_workout_exercise_row(row: dict[str, object]) -> WorkoutExerciseRow:
        """Validate and normalize a raw database row into a typed WorkoutExerciseRow."""
        id_value = row.get("id")
        workout_id = row.get("workout_id")
        exercise_id = row.get("exercise_id")
        order_index = row.get("order_index")
        rest_seconds = row.get("rest_seconds")
        notes = row.get("notes")

        if not isinstance(id_value, int):
            raise WorkoutExerciseRowError.invalid_type("id", "int")
        if not isinstance(workout_id, int):
            raise WorkoutExerciseRowError.invalid_type("workout_id", "int")
        if not isinstance(exercise_id, int):
            raise WorkoutExerciseRowError.invalid_type("exercise_id", "int")
        if not isinstance(order_index, int):
            raise WorkoutExerciseRowError.invalid_type("order_index", "int")
        if rest_seconds is not None and not isinstance(rest_seconds, int):
            raise WorkoutExerciseRowError.invalid_type("rest_seconds", "int | None")
        if notes is not None and not isinstance(notes, str):
            raise WorkoutExerciseRowError.invalid_type("notes", "str | None")

        return WorkoutExerciseRow(
            id=id_value,
            workout_id=workout_id,
            exercise_id=exercise_id,
            order_index=order_index,
            rest_seconds=rest_seconds,
            notes=notes,
        )

    @classmethod
    def _row_to_workout_exercise(
        cls,
        row: dict[str, object],
    ) -> WorkoutExercisePublic:
        """Convert a raw database row into a validated WorkoutExercisePublic model."""
        workout_exercise_row = cls._parse_workout_exercise_row(row)
        return WorkoutExercisePublic.model_validate(workout_exercise_row)
