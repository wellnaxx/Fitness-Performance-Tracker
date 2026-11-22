"""
Meal Service - Business Logic Layer for Meal operations.

This module handles the business logic for meal-related operations including:
- Creating meals
- Retrieving meals
- Updating meals
- Deleting meals

Responsibilities:
- Ensure users only access their own meals
- Coordinate repository operations
"""

import logging
from datetime import date

from core.errors.meal import MealCreationError, MealDeleteError, MealNotFoundError, MealUpdateError
from core.errors.repository import MealRepositoryError
from ports.repositories.meal_repository import MealRepositoryPort
from schemas.meal_schema import MealCreate, MealPublic, MealUpdate
from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET


class MealService:
    def __init__(self, meal_repository: MealRepositoryPort) -> None:
        """
        Initialize MealService with repository dependency.

        Args:
            meal_repository: MealRepositoryPort instance for database operations
        """
        self.meal_repository = meal_repository
        self.logger = logging.getLogger(__name__)

    def create(self, user_id: int, meal_data: MealCreate) -> MealPublic:
        """
        Create a new meal for the user.

        Args:
            user_id: ID of the user creating the meal
            meal_data: MealCreate schema with meal details

        Returns:
            MealPublic schema of the created meal

        Raises:
            MealCreationError: If meal creation fails
        """
        try:
            meal = self.meal_repository.create(user_id, meal_data)
        except MealRepositoryError as exc:
            self.logger.exception("Failed to create meal for user %s!", user_id)
            raise MealCreationError.create_failed() from exc

        self.logger.info("Meal created successfully for user %s with meal ID %s", user_id, meal.id)
        return meal

    def get_by_id(self, user_id: int, meal_id: int) -> MealPublic:
        """
        Retrieve a meal by ID if it belongs to the user.

        Args:
            meal_id: ID of the meal to retrieve
            user_id: ID of the user requesting the meal

        Returns:
            MealPublic schema of the retrieved meal

        Raises:
            MealNotFoundError: If the meal is not found or not visible to the user
        """
        meal = self.meal_repository.get_by_user_and_id(user_id, meal_id)
        if meal is None:
            self.logger.warning("Meal with ID %s not found or not visible to user %s.", meal_id, user_id)
            raise MealNotFoundError.not_found(meal_id=meal_id)

        self.logger.debug("Meal with ID %s retrieved successfully for user %s.", meal_id, user_id)
        return meal

    def list_by_user(
        self,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
        date_from: date | None = None,
        date_to: date | None = None,
        meal_type: str | None = None,
    ) -> list[MealPublic]:
        """
        List meals belonging to the user with pagination and filters.

        Args:
            user_id: ID of the user requesting the meals
            limit: Maximum number of meals to return (default 100)
            offset: Number of meals to skip for pagination (default 0)
            date_from: Optional start date to filter meals
            date_to: Optional end date to filter meals
            meal_type: Optional meal type filter

        Returns:
            List of MealPublic schemas for the user's meals
        """
        meals = self.meal_repository.list_by_user(
            user_id=user_id,
            limit=limit,
            offset=offset,
            date_from=date_from,
            date_to=date_to,
            meal_type=meal_type,
        )
        self.logger.debug(
            "Listed %s meals for user %s with limit %s and offset %s.", len(meals), user_id, limit, offset
        )
        return meals

    def update(self, user_id: int, meal_id: int, meal_data: MealUpdate) -> MealPublic:
        """
        Update a meal by ID if it belongs to the user.

        Args:
            meal_id: ID of the meal to update
            user_id: ID of the user requesting the update
            meal_data: MealUpdate schema with updated meal details

        Returns:
            MealPublic schema of the updated meal

        Raises:
            MealNotFoundError: If the meal is not found or not visible to the user
            MealUpdateError: If the update operation fails
        """
        existing_meal = self.meal_repository.get_by_user_and_id(user_id, meal_id)
        if existing_meal is None:
            self.logger.warning(
                "Meal with ID %s not found or not visible to user %s for update.", meal_id, user_id
            )
            raise MealNotFoundError.not_found(meal_id=meal_id)

        try:
            updated_meal = self.meal_repository.update_owned(user_id, meal_id, meal_data)
        except MealRepositoryError as exc:
            self.logger.exception("Failed to update meal with ID %s for user %s.", meal_id, user_id)
            raise MealUpdateError.update_failed(meal_id=meal_id) from exc

        if updated_meal is None:
            self.logger.warning("Meal with ID %s not found after update attempt for user %s.", meal_id, user_id)
            raise MealNotFoundError.not_accessible(meal_id=meal_id)

        self.logger.info("Meal with ID %s updated successfully for user %s.", meal_id, user_id)
        return updated_meal

    def delete(self, user_id: int, meal_id: int) -> None:
        """Delete a meal by ID if it belongs to the user.

        Args:
            meal_id: ID of the meal to delete
            user_id: ID of the user requesting the deletion

        Raises:
            MealNotFoundError: If the meal is not found or not visible to the user
            MealDeleteError: If the delete operation fails

        Returns:
            None after successful completion.
        """
        existing_meal = self.meal_repository.get_by_user_and_id(user_id, meal_id)
        if existing_meal is None:
            self.logger.warning(
                "Meal with ID %s not found or not visible to user %s for deletion.", meal_id, user_id
            )
            raise MealNotFoundError.not_found(meal_id=meal_id)

        try:
            deleted = self.meal_repository.delete_owned(user_id, meal_id)
        except MealRepositoryError as exc:
            self.logger.exception("Failed to delete meal with ID %s for user %s.", meal_id, user_id)
            raise MealDeleteError.delete_failed(meal_id=meal_id) from exc

        if not deleted:
            self.logger.warning("Meal with ID %s not found after delete attempt for user %s.", meal_id, user_id)
            raise MealNotFoundError.not_accessible(meal_id=meal_id)

        self.logger.info("Meal with ID %s deleted successfully for user %s.", meal_id, user_id)
