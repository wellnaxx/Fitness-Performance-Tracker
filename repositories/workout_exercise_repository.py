"""
Workout Exercise Repository

This module handles all database interactions for the WorkoutExercise entity.
It translates between database rows (now dicts) and Pydantic models.
"""

from __future__ import annotations

from typing import Final, TypedDict

from core.errors.repository import WorkoutExerciseRepositoryError, WorkoutExerciseRowError
from data.executor import (
    execute_insert_tx,
    execute_write_tx,
    fetch_all,
    fetch_one,
    fetch_one_tx,
    transaction_cursor,
)
from schemas.workout_exercises_schema import (
    WorkoutExerciseCreate,
    WorkoutExercisePublic,
    WorkoutExerciseUpdate,
)


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
        workout_id: int,
        workout_exercise_data: WorkoutExerciseCreate,
    ) -> WorkoutExercisePublic:
        """
        Create a workout exercise and shift later order indexes in one transaction.

        Args:
            workout_id: Parent workout ID.
            workout_exercise_data: Workout exercise creation payload.

        Returns:
            The newly created workout exercise.

        Raises:
            WorkoutExerciseRepositoryError: If the inserted row cannot be retrieved afterwards
            or if the transactional write fails.
        """
        try:
            with transaction_cursor() as cursor:
                execute_write_tx(
                    cursor,
                    """
                    UPDATE workout_exercises
                    SET order_index = order_index + 1
                    WHERE workout_id = %s AND order_index >= %s
                    """,
                    (
                        workout_id,
                        workout_exercise_data.order_index,
                    ),
                )

                workout_exercise_id = execute_insert_tx(
                    cursor,
                    """
                    INSERT INTO workout_exercises
                    (workout_id, exercise_id, order_index, rest_seconds, notes)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        workout_id,
                        workout_exercise_data.exercise_id,
                        workout_exercise_data.order_index,
                        workout_exercise_data.rest_seconds,
                        workout_exercise_data.notes,
                    ),
                )

                row = fetch_one_tx(
                    cursor,
                    f"{self._BASE_SELECT} WHERE id = %s",
                    (workout_exercise_id,),
                )
        except WorkoutExerciseRepositoryError:
            raise
        except Exception as exc:
            raise WorkoutExerciseRepositoryError.transaction_failed(exc) from exc

        if row is None:
            raise WorkoutExerciseRepositoryError.inserted_missing(workout_exercise_id)

        return self._row_to_workout_exercise(row)

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

    def update(
        self,
        workout_id: int,
        workout_exercise_id: int,
        update_data: WorkoutExerciseUpdate,
    ) -> WorkoutExercisePublic | None:
        try:
            with transaction_cursor() as cursor:
                existing = fetch_one_tx(
                    cursor,
                    f"{self._BASE_SELECT} WHERE workout_id = %s AND id = %s",
                    (workout_id, workout_exercise_id),
                )
                if existing is None:
                    return None

                existing_exercise = self._row_to_workout_exercise(existing)

                fields = update_data.model_dump(exclude_none=True)
                if not fields:
                    return existing_exercise

                self._validate_update_fields(fields)

                new_order_index = fields.get("order_index")
                if isinstance(new_order_index, int) and new_order_index != existing_exercise.order_index:
                    if new_order_index < existing_exercise.order_index:
                        execute_write_tx(
                            cursor,
                            """
                            UPDATE workout_exercises
                            SET order_index = order_index + 1
                            WHERE workout_id = %s
                            AND order_index >= %s
                            AND order_index < %s
                            """,
                            (
                                workout_id,
                                new_order_index,
                                existing_exercise.order_index,
                            ),
                        )
                    else:
                        execute_write_tx(
                            cursor,
                            """
                            UPDATE workout_exercises
                            SET order_index = order_index - 1
                            WHERE workout_id = %s
                            AND order_index > %s
                            AND order_index <= %s
                            """,
                            (
                                workout_id,
                                existing_exercise.order_index,
                                new_order_index,
                            ),
                        )

                set_clause = ", ".join(f"{field} = %s" for field in fields)
                sql = f"UPDATE workout_exercises SET {set_clause} WHERE workout_id = %s AND id = %s"
                execute_write_tx(cursor, sql, (*fields.values(), workout_id, workout_exercise_id))

                updated_row = fetch_one_tx(
                    cursor,
                    f"{self._BASE_SELECT} WHERE workout_id = %s AND id = %s",
                    (workout_id, workout_exercise_id),
                )
        except WorkoutExerciseRepositoryError:
            raise
        except Exception as exc:
            raise WorkoutExerciseRepositoryError.transaction_failed(exc) from exc

        if updated_row is None:
            raise WorkoutExerciseRepositoryError.updated_missing(workout_exercise_id)

        return self._row_to_workout_exercise(updated_row)

    def delete(self, workout_id: int, workout_exercise_id: int) -> bool:
        """
        Delete a workout exercise and normalize order indexes in one transaction.

        Args:
            workout_id: Parent workout ID.
            workout_exercise_id: Workout exercise ID.

        Returns:
            True if a row was deleted, otherwise False.

        Raises:
            WorkoutExerciseRepositoryError: If the transactional write fails.
        """
        try:
            with transaction_cursor() as cursor:
                deleted = execute_write_tx(
                    cursor,
                    "DELETE FROM workout_exercises WHERE workout_id = %s AND id = %s",
                    (workout_id, workout_exercise_id),
                )

                if deleted > 0:
                    execute_write_tx(
                        cursor,
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

                return deleted > 0
        except WorkoutExerciseRepositoryError:
            raise
        except Exception as exc:
            raise WorkoutExerciseRepositoryError.transaction_failed(exc) from exc

    
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

    def _validate_update_fields(self, fields: dict[str, object]) -> None:
        """Ensure that only allowed fields are being updated."""
        unknown = set(fields) - self._WORKOUT_EXERCISE_UPDATE_WHITELIST
        if unknown:
            raise WorkoutExerciseRepositoryError.invalid_update_fields(unknown)
