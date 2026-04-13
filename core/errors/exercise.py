from __future__ import annotations

from core.errors.base import ServiceError


class ExerciseServiceError(ServiceError):
    """Base error for exercise-related operations."""


class ExerciseNotFoundError(ExerciseServiceError):
    """Raised when an exercise is not found."""

    @classmethod
    def not_found(cls, exercise_id: int) -> ExerciseNotFoundError:
        return cls(f"Exercise with ID {exercise_id} not found.")

    @classmethod
    def not_accessible(cls, exercise_id: int) -> ExerciseNotFoundError:
        return cls(f"Exercise with ID {exercise_id} not found or does not belong to the user.")


class ExerciseCreationError(ExerciseServiceError):
    """Raised when creating an exercise fails."""

    @classmethod
    def create_failed(cls) -> ExerciseCreationError:
        return cls("Failed to create exercise.")


class ExerciseNameAlreadyExistsError(ExerciseServiceError):
    """Raised when an exercise with the same name already exists for the user."""

    @classmethod
    def already_exists(cls, exercise_name: str) -> ExerciseNameAlreadyExistsError:
        return cls(f"An exercise with the name '{exercise_name}' already exists.")


class ExerciseUpdateError(ExerciseServiceError):
    """Raised when updating an exercise fails."""

    @classmethod
    def duplicate_name(cls, exercise_name: str) -> ExerciseUpdateError:
        return cls(f"An exercise with the name '{exercise_name}' already exists.")

    @classmethod
    def update_failed(cls) -> ExerciseUpdateError:
        return cls("Failed to update exercise.")


class ExerciseDeleteError(ExerciseServiceError):
    """Raised when deleting an exercise fails."""

    @classmethod
    def custom_only(cls) -> ExerciseDeleteError:
        return cls("Only custom exercises can be deleted.")

    @classmethod
    def not_accessible(cls, exercise_id: int) -> ExerciseDeleteError:
        return cls(f"Exercise with ID {exercise_id} not found or does not belong to the user.")
