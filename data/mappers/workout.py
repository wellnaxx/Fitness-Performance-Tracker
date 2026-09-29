"""Database row validation and mapping for workout."""

from __future__ import annotations

from datetime import date, datetime
from typing import TypedDict

from core.errors.repository import WorkoutRowError
from schemas.workout_schema import WorkoutPublic


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
    id_value = row.get("id")
    user_id = row.get("user_id")
    name = row.get("name")
    description = row.get("description")
    workout_date = row.get("workout_date")
    started_at = row.get("started_at")
    completed_at = row.get("completed_at")
    notes = row.get("notes")
    created_at = row.get("created_at")
    updated_at = row.get("updated_at")

    if not isinstance(id_value, int):
        raise WorkoutRowError.invalid_type("id", "int")
    if user_id is not None and not isinstance(user_id, int):
        raise WorkoutRowError.invalid_type("user_id", "int | None")
    if not isinstance(name, str):
        raise WorkoutRowError.invalid_type("name", "str")
    if description is not None and not isinstance(description, str):
        raise WorkoutRowError.invalid_type("description", "str | None")
    if not isinstance(workout_date, date):
        raise WorkoutRowError.invalid_type("workout_date", "date")
    if started_at is not None and not isinstance(started_at, datetime):
        raise WorkoutRowError.invalid_type("started_at", "datetime | None")
    if completed_at is not None and not isinstance(completed_at, datetime):
        raise WorkoutRowError.invalid_type("completed_at", "datetime | None")
    if notes is not None and not isinstance(notes, str):
        raise WorkoutRowError.invalid_type("notes", "str | None")
    if not isinstance(created_at, datetime):
        raise WorkoutRowError.invalid_type("created_at", "datetime")
    if not isinstance(updated_at, datetime):
        raise WorkoutRowError.invalid_type("updated_at", "datetime")

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
