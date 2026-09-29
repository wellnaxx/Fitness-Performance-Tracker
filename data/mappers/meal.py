"""Database row validation and mapping for meal."""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from core.errors.repository import MealRowError
from schemas.meal_schema import MealPublic


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
    id_value = row.get("id")
    user_id = row.get("user_id")
    name = row.get("name")
    description = row.get("description")
    eaten_at = row.get("eaten_at")
    meal_type = row.get("meal_type")
    notes = row.get("notes")
    created_at = row.get("created_at")
    updated_at = row.get("updated_at")

    if not isinstance(id_value, int):
        raise MealRowError.invalid_type("id", "int")
    if not isinstance(user_id, int):
        raise MealRowError.invalid_type("user_id", "int")
    if not isinstance(name, str):
        raise MealRowError.invalid_type("name", "str")
    if description is not None and not isinstance(description, str):
        raise MealRowError.invalid_type("description", "str | None")
    if not isinstance(eaten_at, datetime):
        raise MealRowError.invalid_type("eaten_at", "datetime")
    if not isinstance(meal_type, str):
        raise MealRowError.invalid_type("meal_type", "str")
    if notes is not None and not isinstance(notes, str):
        raise MealRowError.invalid_type("notes", "str | None")
    if not isinstance(created_at, datetime):
        raise MealRowError.invalid_type("created_at", "datetime")
    if not isinstance(updated_at, datetime):
        raise MealRowError.invalid_type("updated_at", "datetime")

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
