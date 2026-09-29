"""Database row validation and mapping for meal item."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TypedDict

from core.errors.repository import MealItemRowError
from schemas.meal_item_schema import MealItemPublic


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


def map_meal_item(row: dict[str, object]) -> MealItemPublic:
    """Convert a raw database row into a validated MealItemPublic model."""
    meal_item_row = _parse_meal_item_row(row)
    return MealItemPublic.model_validate(meal_item_row)
