"""Repository contract for WorkoutExercise."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from schemas.workout_exercises_schema import (
        WorkoutExerciseCreate,
        WorkoutExercisePublic,
        WorkoutExerciseUpdate,
    )


class WorkoutExerciseRepositoryPort(Protocol):
    """Persistence operations required by application consumers.

    Implementations preserve the documented ownership and filtering semantics
    and use the existing repository errors for persistence failures.
    """

    def create(self, workout_id: int, workout_exercise_data: WorkoutExerciseCreate) -> WorkoutExercisePublic:
        """Create a workout exercise and shift later order indexes in one transaction.

        Args:
            workout_id: Parent workout ID.
            workout_exercise_data: Workout exercise creation payload.

        Returns:
            The newly created workout exercise.

        Raises:
            WorkoutExerciseRepositoryError: If the inserted row cannot be retrieved afterwards
            or if the transactional write fails.
        """
        ...

    def get_by_id(self, workout_exercise_id: int) -> WorkoutExercisePublic | None:
        """Retrieve a workout exercise by its database ID.

        Args:
            workout_exercise_id: Workout exercise ID.

        Returns:
            The workout exercise if found, otherwise None.

        This lookup does not authorize access; services must verify ownership or visibility.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def get_by_workout_and_id(self, workout_id: int, workout_exercise_id: int) -> WorkoutExercisePublic | None:
        """Retrieve a workout exercise by ID only if it belongs to the workout.

        Args:
            workout_id: Parent workout ID.
            workout_exercise_id: Workout exercise ID.

        Returns:
            The workout exercise if found, otherwise None.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def list_by_workout(self, workout_id: int) -> list[WorkoutExercisePublic]:
        """List workout exercises for a workout.

        Args:
            workout_id: Parent workout ID.

        Returns:
            Workout exercises ordered by `order_index`.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def update(
        self, workout_id: int, workout_exercise_id: int, update_data: WorkoutExerciseUpdate
    ) -> WorkoutExercisePublic | None:
        """Update an item and reorder its siblings in one transaction.

        Args:
            workout_id: Parent workout ID; caller must verify ownership.
            workout_exercise_id: Target workout exercise ID.
            update_data: Partial changes; omitted and None values preserve stored values.

        Returns:
            The updated item, current values for an empty update, or None if absent
            from the workout. A target disappearing during the write rolls back all shifts.

        Raises:
            WorkoutExerciseRepositoryError: If validation, mapping, or the transaction fails.
        """
        ...

    def delete(self, workout_id: int, workout_exercise_id: int) -> bool:
        """Delete a workout exercise and normalize order indexes in one transaction.

        Args:
            workout_id: Parent workout ID.
            workout_exercise_id: Workout exercise ID.

        Returns:
            True if a row was deleted, otherwise False.

        Raises:
            WorkoutExerciseRepositoryError: If the transactional write fails.
        """
        ...
