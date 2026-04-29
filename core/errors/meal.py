from __future__ import annotations

from core.errors.base import ServiceError


class MealCreationError(ServiceError):
    """Raised when creating a meal fails."""

    @classmethod
    def create_failed(cls) -> MealCreationError:
        return cls("Failed to create meal.")
    
class MealNotFoundError(ServiceError):
    """Raised when a meal is not found or not visible to the user."""

    @classmethod
    def not_found(cls, meal_id: int) -> MealNotFoundError:
        return cls(f"Meal with ID {meal_id} not found or does not belong to the user.")
    
    @classmethod
    def not_accessible(cls, meal_id: int) -> MealNotFoundError:
        return cls(f"Meal with ID {meal_id} not accessible or does not belong to the user.")
    
class MealUpdateError(ServiceError):
    """Raised when updating a meal fails."""

    @classmethod
    def update_failed(cls, meal_id: int) -> MealUpdateError:
        return cls(f"Failed to update meal with ID {meal_id}.")
    
class MealDeleteError(ServiceError):
    """Raised when deleting a meal fails."""

    @classmethod
    def delete_failed(cls, meal_id: int) -> MealDeleteError:
        return cls(f"Failed to delete meal with ID {meal_id}.")