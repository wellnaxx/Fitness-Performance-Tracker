"""Database row validation and mapping for meal item."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

from core.errors.repository import MealItemRowError
from data.validation import RowValidator
from schemas.meal_item_schema import MealItemPublic

if TYPE_CHECKING:
    from datetime import datetime

_validator = RowValidator(MealItemRowError)


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

    id_value = _validator.require_int(row.get("id"), "id")
    meal_id = _validator.require_int(row.get("meal_id"), "meal_id")
    name = _validator.require_str(row.get("name"), "name")
    serving_size = _validator.require_optional_numeric(row.get("serving_size"), "serving_size")
    calories = _validator.require_numeric(row.get("calories"), "calories")
    protein = _validator.require_numeric(row.get("protein"), "protein")
    carbs = _validator.require_numeric(row.get("carbs"), "carbs")
    fats = _validator.require_numeric(row.get("fats"), "fats")
    created_at = _validator.require_datetime(row.get("created_at"), "created_at")

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
