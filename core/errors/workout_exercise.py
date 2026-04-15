from __future__ import annotations

from core.errors.base import ServiceError


class WorkoutExerciseValidationError(ServiceError):
    """Raised when workout exercise data fails validation."""

    @classmethod
    def invalid_create_order_index(cls, order_index: int) -> WorkoutExerciseValidationError:
        return cls(f"Invalid order index {order_index} for workout exercise creation.")

    @classmethod
    def invalid_update_order_index(cls, order_index: int) -> WorkoutExerciseValidationError:
        return cls(f"Invalid order index {order_index} for workout exercise update.")


class WorkoutExerciseCreationError(ServiceError):
    """Raised when creating a workout exercise fails."""

    @classmethod
    def create_failed(cls) -> WorkoutExerciseCreationError:
        return cls("Failed to create workout exercise.")


class WorkoutExerciseNotFoundError(ServiceError):
    """Raised when a workout exercise is not found or not visible to the user."""

    @classmethod
    def not_found(cls, workout_exercise_id: int) -> WorkoutExerciseNotFoundError:
        return cls(f"Workout exercise with ID {workout_exercise_id} not found or does not belong to the user.")

    @classmethod
    def not_accessible(cls, workout_exercise_id: int) -> WorkoutExerciseNotFoundError:
        return cls(
            f"Workout exercise with ID {workout_exercise_id} not accessible or does not belong to the user."
        )

    @classmethod
    def not_in_workout(
        cls,
        workout_exercise_id: int,
        workout_id: int,
    ) -> WorkoutExerciseNotFoundError:
        return cls(f"Workout exercise with ID {workout_exercise_id} was not found in workout {workout_id}.")


class WorkoutExerciseUpdateError(ServiceError):
    """Raised when updating a workout exercise fails."""

    @classmethod
    def update_failed(cls, workout_exercise_id: int) -> WorkoutExerciseUpdateError:
        return cls(f"Failed to update workout exercise with ID {workout_exercise_id}.")


class WorkoutExerciseDeleteError(ServiceError):
    """Raised when deleting a workout exercise fails."""

    @classmethod
    def delete_failed(cls, workout_exercise_id: int) -> WorkoutExerciseDeleteError:
        return cls(f"Failed to delete workout exercise with ID {workout_exercise_id}.")
