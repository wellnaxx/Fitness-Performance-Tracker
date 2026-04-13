from __future__ import annotations

from core.errors.base import ServiceError


class WorkoutCreationError(ServiceError):
    """Raised when creating a workout fails."""

    @classmethod
    def create_failed(cls) -> WorkoutCreationError:
        return cls("Failed to create workout.")

class WorkoutNotFoundError(ServiceError):
    """Raised when a workout is not found or not visible to the user."""

    @classmethod
    def not_found(cls, workout_id: int) -> WorkoutNotFoundError:
        return cls(f"Workout with ID {workout_id} not found or does not belong to the user.")
    
    @classmethod
    def not_accessible(cls, workout_id: int) -> WorkoutNotFoundError:
        return cls(f"Workout with ID {workout_id} not accessible or does not belong to the user.")
    

class WorkoutUpdateError(ServiceError):
    """Raised when updating a workout fails."""

    @classmethod
    def update_failed(cls, workout_id: int) -> WorkoutUpdateError:
        return cls(f"Failed to update workout with ID {workout_id}.")
    
class WorkoutDeleteError(ServiceError):
    """Raised when deleting a workout fails."""

    @classmethod
    def delete_failed(cls, workout_id: int) -> WorkoutDeleteError:
        return cls(f"Failed to delete workout with ID {workout_id}.")