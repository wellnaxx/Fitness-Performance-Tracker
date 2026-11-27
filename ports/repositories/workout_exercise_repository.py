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
        """Create an entry and shift later order indexes using the selected executor.

        Ordering writes must use the unit-of-work repository after the service
        locks the owned parent and validates the insertion position. The caller
        owns commit and rollback, including failures during mapping or readback.

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
        """Update an item and reorder siblings using the selected executor.

        The service must lock the parent and validate the position inside a unit
        of work before calling this operation. This method does not commit.

        Args:
            workout_id: Parent workout ID; caller must verify ownership.
            workout_exercise_id: Target workout exercise ID.
            update_data: Partial changes; omitted and None values preserve stored values.

        Returns:
            The updated item, current values for an empty update, or None if absent
            from the workout. The caller must raise on a missing write readback
            inside its unit of work to roll back all shifts.

        Raises:
            WorkoutExerciseRepositoryError: If validation, mapping, or the transaction fails.
        """
        ...

    def delete(self, workout_id: int, workout_exercise_id: int) -> bool:
        """Delete an entry and normalize order indexes using the selected executor.

        Call through the unit of work after locking the owned parent. The caller
        commits only after deletion and normalization both succeed.

        Args:
            workout_id: Parent workout ID.
            workout_exercise_id: Workout exercise ID.

        Returns:
            True if a row was deleted, otherwise False.

        Raises:
            WorkoutExerciseRepositoryError: If the transactional write fails.
        """
        ...
