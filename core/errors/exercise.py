from __future__ import annotations

from core.errors.base import ServiceError


class ExerciseServiceError(ServiceError):
    """Base error for exercise-related operations."""


class ExerciseNotFoundError(ExerciseServiceError):
    """Raised when an exercise is not found."""

    @classmethod
    def not_found(cls, exercise_id: int) -> ExerciseNotFoundError:
        """Build a safe public exercise error.

        Args:
            exercise_id: Requested exercise ID.

        Returns:
            An exercise error with a safe public message.
        """
        return cls(f"Exercise with ID {exercise_id} not found.")

    @classmethod
    def not_accessible(cls, exercise_id: int) -> ExerciseNotFoundError:
        """Build a safe public exercise error.

        Args:
            exercise_id: Requested exercise ID.

        Returns:
            An exercise error with a safe public message.
        """
        return cls(f"Exercise with ID {exercise_id} not found or does not belong to the user.")


class ExerciseCreationError(ExerciseServiceError):
    """Raised when creating an exercise fails."""

    @classmethod
    def create_failed(cls) -> ExerciseCreationError:
        """Build a safe public exercise error.

        Returns:
            An exercise error with a safe public message.
        """
        return cls("Failed to create exercise.")


class ExerciseNameAlreadyExistsError(ExerciseServiceError):
    """Raised when an exercise with the same name already exists for the user."""

    @classmethod
    def already_exists(cls, exercise_name: str) -> ExerciseNameAlreadyExistsError:
        """Build a safe public exercise error.

        Args:
            exercise_name: Name requested for the exercise.

        Returns:
            An exercise error with a safe public message.
        """
        return cls(f"An exercise with the name '{exercise_name}' already exists.")


class ExerciseUpdateError(ExerciseServiceError):
    """An exercise update failed at the persistence layer (HTTP 500)."""

    @classmethod
    def update_failed(cls) -> ExerciseUpdateError:
        """Build a safe public exercise error.

        Returns:
            An exercise error with a safe public message.
        """
        return cls("Failed to update exercise.")


class ExerciseDeleteError(ExerciseServiceError):
    """An exercise deletion failed at the persistence layer (HTTP 500)."""

    @classmethod
    def delete_failed(cls, exercise_id: int) -> ExerciseDeleteError:
        """Build a safe deletion failure for the specified exercise.

        Args:
            exercise_id: Exercise whose deletion failed.

        Returns:
            A public error without database details.
        """
        return cls(f"Failed to delete exercise with ID {exercise_id}.")


class ExerciseValidationError(ExerciseServiceError):
    """An operation violates exercise business rules (HTTP 400)."""

    @classmethod
    def custom_only(cls) -> ExerciseValidationError:
        """Reject deletion of a predefined exercise.

        Returns:
            A validation error explaining that only custom exercises can be deleted.
        """
        return cls("Only custom exercises can be deleted.")
