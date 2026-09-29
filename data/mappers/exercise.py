"""Database row validation and mapping for exercise."""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from core.errors.repository import ExerciseRowError
from schemas.exercise_schema import ExercisePublic


class ExerciseRow(TypedDict):
    id: int
    name: str
    description: str | None
    muscle_group: str
    equipment: str | None
    is_compound: bool
    created_by: int | None
    is_custom: bool
    created_at: datetime
    updated_at: datetime


def _parse_exercise_row(row: dict[str, object]) -> ExerciseRow:
    """Validate and normalize a raw database row into a typed ExerciseRow."""
    id_value = row["id"]
    name = row["name"]
    description = row["description"]
    muscle_group = row["muscle_group"]
    equipment = row["equipment"]
    is_compound = row["is_compound"]
    created_by = row["created_by"]
    is_custom = row["is_custom"]
    created_at = row["created_at"]
    updated_at = row["updated_at"]

    if not isinstance(id_value, int):
        raise ExerciseRowError.invalid_type("id", "int")
    if not isinstance(name, str):
        raise ExerciseRowError.invalid_type("name", "str")
    if description is not None and not isinstance(description, str):
        raise ExerciseRowError.invalid_type("description", "str | None")
    if not isinstance(muscle_group, str):
        raise ExerciseRowError.invalid_type("muscle_group", "str")
    if equipment is not None and not isinstance(equipment, str):
        raise ExerciseRowError.invalid_type("equipment", "str | None")
    if not isinstance(is_compound, bool):
        raise ExerciseRowError.invalid_type("is_compound", "bool")
    if created_by is not None and not isinstance(created_by, int):
        raise ExerciseRowError.invalid_type("created_by", "int | None")
    if not isinstance(is_custom, bool):
        raise ExerciseRowError.invalid_type("is_custom", "bool")
    if not isinstance(created_at, datetime):
        raise ExerciseRowError.invalid_type("created_at", "datetime")
    if not isinstance(updated_at, datetime):
        raise ExerciseRowError.invalid_type("updated_at", "datetime")
    return ExerciseRow(
        id=id_value,
        name=name,
        description=description,
        muscle_group=muscle_group,
        equipment=equipment,
        is_compound=is_compound,
        created_by=created_by,
        is_custom=is_custom,
        created_at=created_at,
        updated_at=updated_at,
    )


def map_exercise(row: dict[str, object]) -> ExercisePublic:
    """Convert a raw database row into a validated ExercisePublic model."""
    exercise_row = _parse_exercise_row(row)
    return ExercisePublic.model_validate(exercise_row)
