"""
Meal Item Repository

This module handles all database interactions for the MealItem entity.
It delegates database row validation and conversion to the dedicated mapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from core.errors.repository import MealItemRepositoryError
from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from data.mappers.meal_item import map_meal_item
from data.queries import QUERIES

if TYPE_CHECKING:
    from schemas.meal_item_schema import MealItemCreate, MealItemPublic, MealItemUpdate


class MealItemRepository:
    """
    Repository for MealItem database operations.

    Responsibilities:
    - Execute SQL queries related to meal items
    - Convert database row dicts to MealItemPublic models
    - Handle all meal-related database logic
    """

    _MEAL_ITEM_UPDATE_WHITELIST: Final[set[str]] = {
        "name",
        "serving_size",
        "calories",
        "protein",
        "carbs",
        "fats",
    }

    def create(self, meal_item_data: MealItemCreate) -> MealItemPublic:
        """
        Create a new item inside a meal.

        Args:
            meal_item_data: Meal item creation payload.

        Returns:
            The newly created meal item.

        Raises:
            MealItemRepositoryError: If the inserted item cannot be retrieved afterwards.
        """
        sql = QUERIES.meal_items.create
        meal_item_id = execute_insert(
            sql,
            (
                meal_item_data.meal_id,
                meal_item_data.name,
                meal_item_data.serving_size,
                meal_item_data.calories,
                meal_item_data.protein,
                meal_item_data.carbs,
                meal_item_data.fats,
            ),
        )

        meal_item = self.get_by_id(meal_item_id)
        if meal_item is None:
            raise MealItemRepositoryError.inserted_missing(meal_item_id)
        return meal_item

    def get_by_id(self, meal_item_id: int) -> MealItemPublic | None:
        """
        Retrieve a meal item by its database ID.

        Args:
            meal_item_id: Meal item ID.

        Returns:
            The meal item if found, otherwise None.
        """
        row = fetch_one(QUERIES.meal_items.get_by_id, (meal_item_id,))
        if row is None:
            return None
        return map_meal_item(row)

    def get_by_meal_and_id(self, meal_id: int, meal_item_id: int) -> MealItemPublic | None:
        """
        Retrieve a meal item by ID only if it belongs to the specified meal.

        Args:
            meal_id: Parent meal ID.
            meal_item_id: Meal item ID.

        Returns:
            The meal item if found in the meal, otherwise None.
        """
        row = fetch_one(
            QUERIES.meal_items.get_by_meal_and_id,
            (meal_id, meal_item_id),
        )
        if row is None:
            return None
        return map_meal_item(row)

    def list_by_meal(self, meal_id: int) -> list[MealItemPublic]:
        """
        List all items for a given meal.

        Args:
            meal_id: Parent meal ID.

        Returns:
            Meal items ordered by insertion ID.
        """
        rows = fetch_all(
            QUERIES.meal_items.list_by_meal,
            (meal_id,),
        )
        return [map_meal_item(row) for row in rows]

    def update_in_meal(
        self,
        meal_id: int,
        meal_item_id: int,
        update_data: MealItemUpdate,
    ) -> MealItemPublic | None:
        """
        Partially update an item within a meal.

        Args:
            meal_id: Parent meal ID.
            meal_item_id: Meal item ID.
            update_data: Partial update payload.

        Returns:
            The updated meal item if found, otherwise None.

        Raises:
            MealItemRepositoryError: If any provided fields are not allowed to be updated.
        """
        fields = update_data.model_dump(exclude_none=True)
        if not fields:
            return self.get_by_meal_and_id(meal_id, meal_item_id)

        unknown = set(fields) - self._MEAL_ITEM_UPDATE_WHITELIST
        if unknown:
            raise MealItemRepositoryError.invalid_update_fields(unknown)

        set_clause = ", ".join(f"{field} = %s" for field in fields)
        sql = QUERIES.meal_items.update_in_meal.format(set_clause=set_clause)
        execute_write(sql, (*fields.values(), meal_id, meal_item_id))
        return self.get_by_meal_and_id(meal_id, meal_item_id)

    def delete_in_meal(self, meal_id: int, meal_item_id: int) -> bool:
        """
        Delete a meal item from the specified meal.

        Args:
            meal_id: Parent meal ID.
            meal_item_id: Meal item ID.

        Returns:
            True if a row was deleted, otherwise False.
        """
        return (
            execute_write(
                QUERIES.meal_items.delete_in_meal,
                (meal_id, meal_item_id),
            )
            > 0
        )
