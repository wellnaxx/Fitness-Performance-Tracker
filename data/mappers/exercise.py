"""Database row validation and mapping for exercise."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from core.errors.repository import ExerciseRowError
from data.validation import RowValidator
from schemas.exercise_schema import ExercisePublic

if TYPE_CHECKING:
    from datetime import datetime

_validator = RowValidator(ExerciseRowError)


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

    id_value = _validator.require_int(id_value, "id")
    name = _validator.require_str(name, "name")
    description = _validator.require_optional_str(description, "description")
    muscle_group = _validator.require_str(muscle_group, "muscle_group")
    equipment = _validator.require_optional_str(equipment, "equipment")
    is_compound = _validator.require_bool(is_compound, "is_compound")
    created_by = _validator.require_optional_int(created_by, "created_by")
    is_custom = _validator.require_bool(is_custom, "is_custom")
    created_at = _validator.require_datetime(created_at, "created_at")
    updated_at = _validator.require_datetime(updated_at, "updated_at")
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
