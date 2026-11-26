"""Repository contract for Meal."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET

if TYPE_CHECKING:
    from datetime import date

    from schemas.meal_schema import MealCreate, MealPublic, MealUpdate


class MealRepositoryPort(Protocol):
    """Persistence operations required by application consumers.

    Implementations preserve the documented ownership and filtering semantics
    and use the existing repository errors for persistence failures.
    """

    def create(self, user_id: int, meal_data: MealCreate) -> MealPublic:
        """Create a new meal for a specific user.

        Args:
            user_id: ID of the user who owns the meal.
            meal_data: Meal creation payload.

        Returns:
            The newly created meal.

        Raises:
            MealRepositoryError: If the inserted meal cannot be retrieved afterwards.
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def get_by_user_and_id(self, user_id: int, meal_id: int) -> MealPublic | None:
        """Retrieve a meal by ID only if it belongs to the specified user.

        Args:
            user_id: Owner user ID.
            meal_id: Meal ID.

        Returns:
            The meal if found and owned by the user, otherwise None.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def list_by_user(
        self,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
        date_from: date | None = None,
        date_to: date | None = None,
        meal_type: str | None = None,
    ) -> list[MealPublic]:
        """List meals for a user with pagination and optional filters.

        Args:
            user_id: Owner user ID.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip.
            date_from: Optional inclusive lower bound for `eaten_at`.
            date_to: Optional inclusive upper bound for `eaten_at`.
            meal_type: Optional meal type filter.

        Returns:
            A list of meals ordered from newest to oldest.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def update_owned(self, user_id: int, meal_id: int, update_data: MealUpdate) -> MealPublic | None:
        """Partially update a meal owned by the specified user.

        Args:
            user_id: Owner user ID.
            meal_id: Meal ID.
            update_data: Partial update payload.

        Returns:
            The updated meal if it exists and belongs to the user, otherwise None.

        Raises:
            MealRepositoryError: If any provided fields are not allowed to be updated.
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def delete_owned(self, user_id: int, meal_id: int) -> bool:
        """Delete a meal owned by the specified user.

        Args:
            user_id: Owner user ID.
            meal_id: Meal ID.

        Returns:
            True if a row was deleted, otherwise False.

        Raises:
            DatabaseError: If the database operation fails.
        """
        ...
