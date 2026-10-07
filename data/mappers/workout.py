"""Database row validation and mapping for workout."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from core.errors.repository import WorkoutRowError
from data.validation import RowValidator
from schemas.workout_schema import WorkoutPublic

if TYPE_CHECKING:
    from datetime import date, datetime

_validator = RowValidator(WorkoutRowError)


class WorkoutRow(TypedDict):
    id: int
    user_id: int | None
    name: str
    description: str | None
    workout_date: date
    started_at: datetime | None
    completed_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


def _parse_workout_row(row: dict[str, object]) -> WorkoutRow:
    """Validate and normalize a raw database row into a typed WorkoutRow."""

    id_value = _validator.require_int(row.get("id"), "id")
    user_id = _validator.require_optional_int(row.get("user_id"), "user_id")
    name = _validator.require_str(row.get("name"), "name")
    description = _validator.require_optional_str(row.get("description"), "description")
    workout_date = _validator.require_date(row.get("workout_date"), "workout_date")
    started_at = _validator.require_optional_datetime(row.get("started_at"), "started_at")
    completed_at = _validator.require_optional_datetime(row.get("completed_at"), "completed_at")
    notes = _validator.require_optional_str(row.get("notes"), "notes")
    created_at = _validator.require_datetime(row.get("created_at"), "created_at")
    updated_at = _validator.require_datetime(row.get("updated_at"), "updated_at")

    return WorkoutRow(
        id=id_value,
        user_id=user_id,
        name=name,
        description=description,
        workout_date=workout_date,
        started_at=started_at,
        completed_at=completed_at,
        notes=notes,
        created_at=created_at,
        updated_at=updated_at,
    )


def map_workout(row: dict[str, object]) -> WorkoutPublic:
    """Convert a raw database row into a validated WorkoutPublic model."""
    workout_row = _parse_workout_row(row)
    return WorkoutPublic.model_validate(workout_row)
