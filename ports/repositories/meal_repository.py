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
        """Create a new meal for a specific user."""
        ...

    def get_by_user_and_id(self, user_id: int, meal_id: int) -> MealPublic | None:
        """Retrieve a meal by ID only if it belongs to the specified user."""
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
        """List meals for a user with pagination and optional filters."""
        ...

    def update_owned(self, user_id: int, meal_id: int, update_data: MealUpdate) -> MealPublic | None:
        """Partially update a meal owned by the specified user."""
        ...

    def delete_owned(self, user_id: int, meal_id: int) -> bool:
        """Delete a meal owned by the specified user."""
        ...
