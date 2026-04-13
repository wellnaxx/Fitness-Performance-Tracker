from __future__ import annotations

from core.errors.base import ServiceError


class WorkoutCreationError(ServiceError):
    """Raised when creating a workout fails."""

    @classmethod
    def create_failed(cls) -> WorkoutCreationError:
        return cls("Failed to create workout.")
