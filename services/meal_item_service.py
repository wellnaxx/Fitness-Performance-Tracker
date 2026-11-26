"""Meal-item operations guarded by ownership of the parent meal."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.errors.meal_item import (
    MealItemCreationError,
    MealItemDeleteError,
    MealItemNotFoundError,
    MealItemUpdateError,
)
from core.errors.repository import MealItemRepositoryError
from services.ownership import require_owned_meal

if TYPE_CHECKING:
    from ports.repositories.meal_item_repository import MealItemRepositoryPort
    from ports.repositories.meal_repository import MealRepositoryPort
    from schemas.meal_item_schema import MealItemCreate, MealItemPublic, MealItemUpdate


class MealItemService:
    """Authorize parent meals before reading or changing their items.

    Request schemas validate item fields. Items have no position field and are
    listed in repository order, by ascending ID. Persistence and row-validation
    failures propagate unless explicitly translated into a service error below.
    """

    def __init__(
        self, meal_repository: MealRepositoryPort, meal_item_repository: MealItemRepositoryPort
    ) -> None:
        """Initialize the service with repository contracts.

        Args:
            meal_repository: Persistence used to verify parent meal ownership.
            meal_item_repository: Persistence for meal-scoped item operations.
        """
        self.meal_repo = meal_repository
        self.meal_item_repo = meal_item_repository
        self.logger = logging.getLogger(__name__)

    def create(self, user_id: int, meal_item_data: MealItemCreate) -> MealItemPublic:
        """Create an item after verifying ownership of the payload's meal.

        Args:
            user_id: Authenticated user ID.
            meal_item_data: Validated name, nutrition values, optional serving size,
                and parent meal ID. Zero nutrition values are allowed.

        Returns:
            The persisted item, including its assigned ID and creation timestamp.

        Raises:
            MealNotFoundError: If the meal is missing or belongs to another user.
            MealItemCreationError: If the item repository reports a creation failure.
            DatabaseError: If a database operation fails.
            RowValidationError: If a stored row cannot be mapped to a valid item or meal.
            MealRepositoryError: If the ownership lookup fails at the repository level.
        """
        require_owned_meal(self.meal_repo, user_id, meal_item_data.meal_id, logger=self.logger)

        try:
            meal_item = self.meal_item_repo.create(meal_item_data)
        except MealItemRepositoryError as exc:
            self.logger.exception(
                "Failed to add meal item | meal_id=%s user_id=%s", meal_item_data.meal_id, user_id
            )
            raise MealItemCreationError.create_failed() from exc

        self.logger.info(
            "Meal item created | meal_item_id=%s meal_id=%s user_id=%s",
            meal_item.id,
            meal_item_data.meal_id,
            user_id,
        )
        return meal_item

    def get_by_id(self, user_id: int, meal_id: int, meal_item_id: int) -> MealItemPublic:
        """Retrieve an item within an owned meal.

        Args:
            user_id: Authenticated user ID.
            meal_id: Parent meal ID whose ownership must be verified.
            meal_item_id: Requested item ID.

        Returns:
            The item belonging to the specified meal.

        Raises:
            MealNotFoundError: If the meal is missing or belongs to another user.
            MealItemNotFoundError: If the item is missing or belongs to another meal.
            DatabaseError: If a database lookup fails.
            RowValidationError: If a stored item or meal row is invalid.
            RepositoryError: If either repository reports a lookup failure.
        """
        require_owned_meal(self.meal_repo, user_id, meal_id, logger=self.logger)

        meal_item = self.meal_item_repo.get_by_meal_and_id(meal_id, meal_item_id)
        if meal_item is None:
            self.logger.warning("Meal item not found | meal_item_id=%s meal_id=%s", meal_item_id, meal_id)
            raise MealItemNotFoundError.not_in_meal(meal_item_id, meal_id)

        self.logger.debug(
            "Meal item retrieved | meal_item_id=%s meal_id=%s user_id=%s", meal_item_id, meal_id, user_id
        )
        return meal_item

    def list_by_meal(self, user_id: int, meal_id: int) -> list[MealItemPublic]:
        """List all items in an owned meal without pagination.

        Args:
            user_id: Authenticated user ID.
            meal_id: Parent meal ID whose ownership must be verified.

        Returns:
            Items in ascending ID order, or an empty list for an owned meal with no items.

        Raises:
            MealNotFoundError: If the meal is missing or belongs to another user.
            DatabaseError: If a database lookup fails.
            RowValidationError: If a stored item or meal row is invalid.
            RepositoryError: If either repository reports a lookup failure.
        """
        require_owned_meal(self.meal_repo, user_id, meal_id, logger=self.logger)

        meal_items = self.meal_item_repo.list_by_meal(meal_id)
        self.logger.debug(
            "Meal items listed | count=%s meal_id=%s user_id=%s", len(meal_items), meal_id, user_id
        )
        return meal_items

    def update(
        self,
        user_id: int,
        meal_id: int,
        meal_item_id: int,
        meal_item_update_data: MealItemUpdate,
    ) -> MealItemPublic:
        """Partially update an existing item within an owned meal.

        Args:
            user_id: Authenticated user ID.
            meal_id: Parent meal ID whose ownership must be verified.
            meal_item_id: Item to update within that meal.
            meal_item_update_data: Validated changes. Omitted and None-valued fields
                preserve stored values; zero values are applied. The meal ID cannot change.

        Returns:
            The updated item, or current values for an empty or all-None update.

        Raises:
            MealNotFoundError: If the meal is missing or belongs to another user.
            MealItemNotFoundError: If the item is absent from the meal or disappears
                before the update readback.
            MealItemUpdateError: If the item repository reports an update failure.
            DatabaseError: If a database operation fails.
            RowValidationError: If a stored item or meal row is invalid.
            RepositoryError: If a repository lookup fails before the update.
        """
        require_owned_meal(self.meal_repo, user_id, meal_id, logger=self.logger)

        meal_item = self.meal_item_repo.get_by_meal_and_id(meal_id, meal_item_id)
        if meal_item is None:
            self.logger.warning("Meal item not found | meal_item_id=%s meal_id=%s", meal_item_id, meal_id)
            raise MealItemNotFoundError.not_in_meal(meal_item_id, meal_id)

        try:
            updated = self.meal_item_repo.update_in_meal(meal_id, meal_item_id, meal_item_update_data)
        except MealItemRepositoryError as exc:
            self.logger.exception("Meal item update failed | meal_item_id=%s user_id=%s", meal_item_id, user_id)
            raise MealItemUpdateError.update_failed(meal_item_id) from exc

        if updated is None:
            self.logger.warning(
                "Meal item missing after update | meal_item_id=%s meal_id=%s user_id=%s",
                meal_item_id,
                meal_id,
                user_id,
            )
            raise MealItemNotFoundError.not_accessible(meal_item_id)

        self.logger.info(
            "Meal item updated | meal_item_id=%s meal_id=%s user_id=%s", meal_item_id, meal_id, user_id
        )
        return updated

    def delete(self, user_id: int, meal_id: int, meal_item_id: int) -> None:
        """Delete an existing item within an owned meal.

        Args:
            user_id: Authenticated user ID.
            meal_id: Parent meal ID whose ownership must be verified.
            meal_item_id: Item to delete within that meal.

        Returns:
            None after deleting the item.

        Raises:
            MealNotFoundError: If the meal is missing or belongs to another user.
            MealItemNotFoundError: If the item is absent from the meal or the delete
                affects no row after the existence check.
            MealItemDeleteError: If the item repository reports a deletion failure.
            DatabaseError: If a database operation fails.
            RowValidationError: If a stored item or meal row is invalid.
            RepositoryError: If a repository lookup fails before deletion.
        """
        require_owned_meal(self.meal_repo, user_id, meal_id, logger=self.logger)

        meal_item = self.meal_item_repo.get_by_meal_and_id(meal_id, meal_item_id)
        if meal_item is None:
            self.logger.warning("Meal item not found | meal_item_id=%s meal_id=%s", meal_item_id, meal_id)
            raise MealItemNotFoundError.not_in_meal(meal_item_id, meal_id)

        try:
            deleted = self.meal_item_repo.delete_in_meal(meal_id, meal_item_id)
        except MealItemRepositoryError as exc:
            self.logger.exception("Meal item delete failed | meal_item_id=%s user_id=%s", meal_item_id, user_id)
            raise MealItemDeleteError.delete_failed(meal_item_id) from exc

        if not deleted:
            self.logger.warning(
                "Meal item missing during delete | meal_item_id=%s meal_id=%s user_id=%s",
                meal_item_id,
                meal_id,
                user_id,
            )
            raise MealItemNotFoundError.not_accessible(meal_item_id)

        self.logger.info(
            "Meal item deleted | meal_item_id=%s meal_id=%s user_id=%s", meal_item_id, meal_id, user_id
        )
