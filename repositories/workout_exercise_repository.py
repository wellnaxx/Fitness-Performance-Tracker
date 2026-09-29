"""
Workout Exercise Repository

This module handles all database interactions for the WorkoutExercise entity.
It delegates database row validation and conversion to the dedicated mapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from core.errors.repository import WorkoutExerciseRepositoryError
from data.executor import (
    execute_insert_tx,
    execute_write_tx,
    fetch_all,
    fetch_one,
    fetch_one_tx,
    transaction_cursor,
)
from data.mappers.workout_exercise import map_workout_exercise
from data.queries import QUERIES

if TYPE_CHECKING:
    from schemas.workout_exercises_schema import (
        WorkoutExerciseCreate,
        WorkoutExercisePublic,
        WorkoutExerciseUpdate,
    )


class WorkoutExerciseRepository:
    """
    Repository for WorkoutExercise database operations.

    Responsibilities:
    - Execute SQL queries related to workout exercises
    - Convert database row dicts to WorkoutExercisePublic models
    - Handle all workout-exercise-related database logic
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
                    QUERIES.workout_exercises.shift_for_insert,
                    (
                        workout_id,
                        workout_exercise_data.order_index,
                    ),
                )

                workout_exercise_id = execute_insert_tx(
                    cursor,
                    QUERIES.workout_exercises.create,
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
                    QUERIES.workout_exercises.get_by_id,
                    (workout_exercise_id,),
                )
        except WorkoutExerciseRepositoryError:
            raise
        except Exception as exc:
            raise WorkoutExerciseRepositoryError.transaction_failed(exc) from exc

        if row is None:
            raise WorkoutExerciseRepositoryError.inserted_missing(workout_exercise_id)

        return map_workout_exercise(row)

    def get_by_id(self, workout_exercise_id: int) -> WorkoutExercisePublic | None:
        """
        Retrieve a workout exercise by its database ID.

        Args:
            workout_exercise_id: Workout exercise ID.

        Returns:
            The workout exercise if found, otherwise None.
        """
        row = fetch_one(QUERIES.workout_exercises.get_by_id, (workout_exercise_id,))
        if row is None:
            return None
        return map_workout_exercise(row)

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
            QUERIES.workout_exercises.get_by_workout_and_id,
            (workout_id, workout_exercise_id),
        )
        if row is None:
            return None
        return map_workout_exercise(row)

    def list_by_workout(self, workout_id: int) -> list[WorkoutExercisePublic]:
        """
        List workout exercises for a workout.

        Args:
            workout_id: Parent workout ID.

        Returns:
            Workout exercises ordered by `order_index`.
        """
        rows = fetch_all(
            QUERIES.workout_exercises.list_by_workout,
            (workout_id,),
        )
        return [map_workout_exercise(row) for row in rows]

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
                    QUERIES.workout_exercises.get_by_workout_and_id,
                    (workout_id, workout_exercise_id),
                )
                if existing is None:
                    return None

                existing_exercise = map_workout_exercise(existing)

                fields = update_data.model_dump(exclude_none=True)
                if not fields:
                    return existing_exercise

                self._validate_update_fields(fields)

                new_order_index = fields.get("order_index")
                if isinstance(new_order_index, int) and new_order_index != existing_exercise.order_index:
                    if new_order_index < existing_exercise.order_index:
                        execute_write_tx(
                            cursor,
                            QUERIES.workout_exercises.shift_toward_end,
                            (
                                workout_id,
                                new_order_index,
                                existing_exercise.order_index,
                            ),
                        )
                    else:
                        execute_write_tx(
                            cursor,
                            QUERIES.workout_exercises.shift_toward_start,
                            (
                                workout_id,
                                existing_exercise.order_index,
                                new_order_index,
                            ),
                        )

                set_clause = ", ".join(f"{field} = %s" for field in fields)
                sql = QUERIES.workout_exercises.update.format(set_clause=set_clause)
                execute_write_tx(cursor, sql, (*fields.values(), workout_id, workout_exercise_id))

                updated_row = fetch_one_tx(
                    cursor,
                    QUERIES.workout_exercises.get_by_workout_and_id,
                    (workout_id, workout_exercise_id),
                )
        except WorkoutExerciseRepositoryError:
            raise
        except Exception as exc:
            raise WorkoutExerciseRepositoryError.transaction_failed(exc) from exc

        if updated_row is None:
            raise WorkoutExerciseRepositoryError.updated_missing(workout_exercise_id)

        return map_workout_exercise(updated_row)

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
                    QUERIES.workout_exercises.delete,
                    (workout_id, workout_exercise_id),
                )

                if deleted > 0:
                    execute_write_tx(
                        cursor,
                        QUERIES.workout_exercises.normalize_order_indexes,
                        (workout_id,),
                    )

                return deleted > 0
        except WorkoutExerciseRepositoryError:
            raise
        except Exception as exc:
            raise WorkoutExerciseRepositoryError.transaction_failed(exc) from exc

    def _validate_update_fields(self, fields: dict[str, object]) -> None:
        """Ensure that only allowed fields are being updated."""
        unknown = set(fields) - self._WORKOUT_EXERCISE_UPDATE_WHITELIST
        if unknown:
            raise WorkoutExerciseRepositoryError.invalid_update_fields(unknown)
