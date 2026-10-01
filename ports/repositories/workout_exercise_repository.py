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
        """Create a workout exercise and shift later order indexes in one transaction."""
        ...

    def get_by_workout_and_id(self, workout_id: int, workout_exercise_id: int) -> WorkoutExercisePublic | None:
        """Retrieve a workout exercise by ID only if it belongs to the workout."""
        ...

    def list_by_workout(self, workout_id: int) -> list[WorkoutExercisePublic]:
        """List workout exercises for a workout."""
        ...

    def update(
        self, workout_id: int, workout_exercise_id: int, update_data: WorkoutExerciseUpdate
    ) -> WorkoutExercisePublic | None:
        """Update an exercise within its workout and adjust ordering atomically."""
        ...

    def delete(self, workout_id: int, workout_exercise_id: int) -> bool:
        """Delete a workout exercise and normalize order indexes in one transaction."""
        ...
