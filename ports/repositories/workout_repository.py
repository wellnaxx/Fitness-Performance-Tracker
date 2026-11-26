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
        """Create a new workout for a specific user.

        Args:
            user_id: Owner user ID.
            workout_data: Workout creation payload.

        Returns:
            The newly created workout.

        Raises:
            WorkoutRepositoryError: If the inserted row cannot be retrieved afterwards.
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def get_by_user_and_id(self, user_id: int, workout_id: int) -> WorkoutPublic | None:
        """Retrieve a workout by ID only if it belongs to the user.

        Args:
            user_id: Owner user ID.
            workout_id: Workout ID.

        Returns:
            The workout if found and owned by the user, otherwise None.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def update_owned(self, user_id: int, workout_id: int, update_data: WorkoutUpdate) -> WorkoutPublic | None:
        """Partially update a workout owned by the user.

        Args:
            user_id: Owner user ID.
            workout_id: Workout ID.
            update_data: Partial update payload.

        Returns:
            The updated workout if found, otherwise None.

        Raises:
            WorkoutRepositoryError: If any provided fields are not allowed to be updated.
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def delete_owned(self, user_id: int, workout_id: int) -> bool:
        """Delete a workout owned by the user.

        Args:
            user_id: Owner user ID.
            workout_id: Workout ID.

        Returns:
            True if a row was deleted, otherwise False.

        Raises:
            DatabaseError: If the database operation fails.
        """
        ...

    def get_visible_by_id(self, user_id: int, workout_id: int) -> WorkoutPublic | None:
        """Retrieve a workout by ID if it is globally visible or owned by the user.

        Args:
            workout_id: Workout ID.
            user_id: Requesting user ID.

        Returns:
            The workout if visible to the user, otherwise None.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def get_all_visible_for_user(
        self,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
        search: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[WorkoutPublic]:
        """List workouts for a user with optional search filtering.

        Args:
            user_id: Owner user ID.
            search: Optional case-insensitive name/description filter.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip.
            date_from: Optional inclusive lower bound for `workout_date`.
            date_to: Optional inclusive upper bound for `workout_date`.

        Returns:
            Workouts ordered from newest to oldest.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...
