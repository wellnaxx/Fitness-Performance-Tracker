"""Public meal-item service errors translated by the shared HTTP handlers."""

from __future__ import annotations

from core.errors.base import ServiceError


class MealItemCreationError(ServiceError):
    """Creating a meal item failed (HTTP 500)."""

    @classmethod
    def create_failed(cls) -> MealItemCreationError:
        """Build a creation failure without exposing persistence details.

        Returns:
            A safe public creation error.
        """
        return cls("Failed to create meal item.")


class MealItemNotFoundError(ServiceError):
    """A requested item is missing or inaccessible (HTTP 404)."""

    @classmethod
    def not_found(cls, meal_item_id: int) -> MealItemNotFoundError:
        """Build an error for a missing or unowned item.

        Args:
            meal_item_id: Requested meal item ID.

        Returns:
            An error that does not distinguish missing items from another user's items.
        """
        return cls(f"Meal item with ID {meal_item_id} not found or does not belong to the user.")

    @classmethod
    def not_accessible(cls, meal_item_id: int) -> MealItemNotFoundError:
        """Build an error for an item inaccessible during an operation.

        Args:
            meal_item_id: Item that is inaccessible or disappeared during a write.

        Returns:
            An error combining missing-item and ownership rejection semantics.
        """
        return cls(f"Meal item with ID {meal_item_id} not accessible or does not belong to the user.")

    @classmethod
    def not_in_meal(cls, meal_item_id: int, meal_id: int) -> MealItemNotFoundError:
        """Build an error for an item absent from an accessible meal.

        Args:
            meal_item_id: Requested item ID.
            meal_id: Parent meal ID whose ownership the caller has already verified.

        Returns:
            An error identifying the requested item and meal without exposing another meal's data.
        """
        return cls(f"Meal item with ID {meal_item_id} was not found in meal {meal_id}.")


class MealItemUpdateError(ServiceError):
    """Updating a meal item failed (HTTP 500)."""

    @classmethod
    def update_failed(cls, meal_item_id: int) -> MealItemUpdateError:
        """Build an update failure without exposing persistence details.

        Args:
            meal_item_id: Item whose update failed.

        Returns:
            A safe public update error identifying the item.
        """
        return cls(f"Failed to update meal item with ID {meal_item_id}.")


class MealItemDeleteError(ServiceError):
    """Deleting a meal item failed (HTTP 500)."""

    @classmethod
    def delete_failed(cls, meal_item_id: int) -> MealItemDeleteError:
        """Build a deletion failure without exposing persistence details.

        Args:
            meal_item_id: Item whose deletion failed.

        Returns:
            A safe public deletion error identifying the item.
        """
        return cls(f"Failed to delete meal item with ID {meal_item_id}.")
