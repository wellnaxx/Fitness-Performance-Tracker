"""Database row validation and mapping for meal."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from core.errors.repository import MealRowError
from data.validation import RowValidator
from schemas.meal_schema import MealPublic

if TYPE_CHECKING:
    from datetime import datetime

_validator = RowValidator(MealRowError)


class MealRow(TypedDict):
    id: int
    user_id: int
    name: str
    description: str | None
    eaten_at: datetime
    meal_type: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


def _parse_meal_row(row: dict[str, object]) -> MealRow:
    """Validate and normalize a raw database row into a typed MealRow."""

    id_value = _validator.require_int(row.get("id"), "id")
    user_id = _validator.require_int(row.get("user_id"), "user_id")
    name = _validator.require_str(row.get("name"), "name")
    description = _validator.require_optional_str(row.get("description"), "description")
    eaten_at = _validator.require_datetime(row.get("eaten_at"), "eaten_at")
    meal_type = _validator.require_str(row.get("meal_type"), "meal_type")
    notes = _validator.require_optional_str(row.get("notes"), "notes")
    created_at = _validator.require_datetime(row.get("created_at"), "created_at")
    updated_at = _validator.require_datetime(row.get("updated_at"), "updated_at")

    return MealRow(
        id=id_value,
        user_id=user_id,
        name=name,
        description=description,
        eaten_at=eaten_at,
        meal_type=meal_type,
        notes=notes,
        created_at=created_at,
        updated_at=updated_at,
    )


def map_meal(row: dict[str, object]) -> MealPublic:
    """Convert a raw database row into a validated MealPublic model."""
    meal_row = _parse_meal_row(row)
    return MealPublic.model_validate(meal_row)
