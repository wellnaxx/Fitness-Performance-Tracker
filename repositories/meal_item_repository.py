"""
Meal Item Repository

This module handles all database interactions for the MealItem entity.
It translates between database rows (now dicts) and Pydantic models.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Final, TypedDict

from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from schemas.meal_item_schema import MealItemCreate, MealItemPublic, MealItemUpdate
from utils.errors import MealItemRepositoryError, MealItemRowError


class MealItemRow(TypedDict):
    id: int
    meal_id: int
    name: str
    serving_size: Decimal | None
    calories: Decimal
    protein: Decimal
    carbs: Decimal
    fats: Decimal
    created_at: datetime


class MealItemRepository:
    """
    Repository for MealItem database operations.

    Responsibilities:
    - Execute SQL queries related to meal items
    - Convert database row dicts to MealItemPublic models
    - Handle all meal-related database logic
    """

    _BASE_SELECT: Final[str] = """
        SELECT id, meal_id, name, serving_size, calories, protein, carbs, fats, created_at
        FROM meal_items
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
        sql = """
            INSERT INTO meal_items
            (meal_id, name, serving_size, calories, protein, carbs, fats)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
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
        row = fetch_one(f"{self._BASE_SELECT} WHERE id = %s", (meal_item_id,))
        if row is None:
            return None
        return self._row_to_meal_item(row)

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
            f"{self._BASE_SELECT} WHERE meal_id = %s AND id = %s",
            (meal_id, meal_item_id),
        )
        if row is None:
            return None
        return self._row_to_meal_item(row)

    def list_by_meal(self, meal_id: int) -> list[MealItemPublic]:
        """
        List all items for a given meal.

        Args:
            meal_id: Parent meal ID.

        Returns:
            Meal items ordered by insertion ID.
        """
        rows = fetch_all(
            f"{self._BASE_SELECT} WHERE meal_id = %s ORDER BY id ASC",
            (meal_id,),
        )
        return [self._row_to_meal_item(row) for row in rows]

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
        sql = f"UPDATE meal_items SET {set_clause} WHERE meal_id = %s AND id = %s"
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
                "DELETE FROM meal_items WHERE meal_id = %s AND id = %s",
                (meal_id, meal_item_id),
            )
            > 0
        )

    @staticmethod
    def _parse_meal_item_row(row: dict[str, object]) -> MealItemRow:
        """Validate and normalize a raw database row into a typed MealItemRow."""
        id_value = row.get("id")
        meal_id = row.get("meal_id")
        name = row.get("name")
        serving_size = row.get("serving_size")
        calories = row.get("calories")
        protein = row.get("protein")
        carbs = row.get("carbs")
        fats = row.get("fats")
        created_at = row.get("created_at")

        if not isinstance(id_value, int):
            raise MealItemRowError.invalid_type("id", "int")
        if not isinstance(meal_id, int):
            raise MealItemRowError.invalid_type("meal_id", "int")
        if not isinstance(name, str):
            raise MealItemRowError.invalid_type("name", "str")
        if serving_size is not None and not isinstance(serving_size, (Decimal, int, float)):
            raise MealItemRowError.invalid_type("serving_size", "numeric | None")
        if not isinstance(calories, (Decimal, int, float)):
            raise MealItemRowError.invalid_type("calories", "numeric")
        if not isinstance(protein, (Decimal, int, float)):
            raise MealItemRowError.invalid_type("protein", "numeric")
        if not isinstance(carbs, (Decimal, int, float)):
            raise MealItemRowError.invalid_type("carbs", "numeric")
        if not isinstance(fats, (Decimal, int, float)):
            raise MealItemRowError.invalid_type("fats", "numeric")
        if not isinstance(created_at, datetime):
            raise MealItemRowError.invalid_type("created_at", "datetime")

        return MealItemRow(
            id=id_value,
            meal_id=meal_id,
            name=name,
            serving_size=None if serving_size is None else Decimal(str(serving_size)),
            calories=Decimal(str(calories)),
            protein=Decimal(str(protein)),
            carbs=Decimal(str(carbs)),
            fats=Decimal(str(fats)),
            created_at=created_at,
        )

    @classmethod
    def _row_to_meal_item(cls, row: dict[str, object]) -> MealItemPublic:
        """Convert a raw database row into a validated MealItemPublic model."""
        meal_item_row = cls._parse_meal_item_row(row)
        return MealItemPublic.model_validate(meal_item_row)
