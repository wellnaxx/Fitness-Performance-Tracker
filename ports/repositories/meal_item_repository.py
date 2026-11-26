"""Persistence contract for items belonging to a meal."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from schemas.meal_item_schema import MealItemCreate, MealItemPublic, MealItemUpdate


class MealItemRepositoryPort(Protocol):
    """Store and retrieve meal items with operations scoped to their parent meal.

    Meal scoping does not verify user ownership. Services must verify access to
    the parent meal before exposing or modifying its items. Implementations
    propagate database, row-validation, and repository errors on persistence failures.
    """

    def create(self, meal_item_data: MealItemCreate) -> MealItemPublic:
        """Create an item within the meal specified by the payload.

        Args:
            meal_item_data: Validated item values and parent meal ID.

        Returns:
            The persisted item with its assigned ID and creation timestamp.

        Raises:
            MealItemRepositoryError: If the inserted item cannot be retrieved afterwards.
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def get_by_id(self, meal_item_id: int) -> MealItemPublic | None:
        """Retrieve an item without checking parent meal or user ownership.

        Args:
            meal_item_id: Item ID. Callers must separately verify access to its meal.

        Returns:
            The matching item, or None if it does not exist.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def get_by_meal_and_id(self, meal_id: int, meal_item_id: int) -> MealItemPublic | None:
        """Retrieve an item within the specified meal.

        Args:
            meal_id: Parent meal ID.
            meal_item_id: Item ID.

        Returns:
            The matching item, or None if missing or belonging to another meal.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def list_by_meal(self, meal_id: int) -> list[MealItemPublic]:
        """List all items within a meal without pagination.

        Args:
            meal_id: Parent meal ID.

        Returns:
            Items in ascending ID order, or an empty list when none match.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def update_in_meal(
        self,
        meal_id: int,
        meal_item_id: int,
        update_data: MealItemUpdate,
    ) -> MealItemPublic | None:
        """Partially update an item within its parent meal.

        Args:
            meal_id: Parent meal ID.
            meal_item_id: Item ID.
            update_data: Item changes. Omitted and None-valued fields preserve stored values.

        Returns:
            The updated item, current values for an empty update, or None if missing
            or belonging to another meal.

        Raises:
            MealItemRepositoryError: If unsupported update fields are supplied.
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def delete_in_meal(self, meal_id: int, meal_item_id: int) -> bool:
        """Delete an item within the specified meal.

        Args:
            meal_id: Parent meal ID.
            meal_item_id: Item ID.

        Returns:
            True if deleted; False if missing or belonging to another meal.

        Raises:
            DatabaseError: If the database operation fails.
        """
        ...
