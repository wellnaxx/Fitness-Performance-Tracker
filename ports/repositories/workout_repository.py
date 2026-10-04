"""Repository contract for Workout."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET

if TYPE_CHECKING:
    from datetime import date

    from schemas.workout_schema import WorkoutCreate, WorkoutPublic, WorkoutUpdate


class WorkoutRepositoryPort(Protocol):
    """Persistence operations required by application consumers.

    Implementations preserve the documented ownership and filtering semantics
    and use the existing repository errors for persistence failures.
    """

    def create(self, user_id: int, workout_data: WorkoutCreate) -> WorkoutPublic:
        """Create a new workout for a specific user."""
        ...

    def get_by_user_and_id(self, user_id: int, workout_id: int) -> WorkoutPublic | None:
        """Retrieve a workout by ID only if it belongs to the user."""
        ...

    def update_owned(self, user_id: int, workout_id: int, update_data: WorkoutUpdate) -> WorkoutPublic | None:
        """Partially update a workout owned by the user."""
        ...

    def delete_owned(self, user_id: int, workout_id: int) -> bool:
        """Delete a workout owned by the user."""
        ...

    def get_visible_by_id(self, workout_id: int, user_id: int) -> WorkoutPublic | None:
        """Retrieve a workout by ID if it is globally visible or owned by the user."""
        ...

    def get_all_visible_for_user(
        self,
        user_id: int,
        search: str | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[WorkoutPublic]:
        """List workouts for a user with optional search filtering."""
        ...
