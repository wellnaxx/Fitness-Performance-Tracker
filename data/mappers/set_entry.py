"""Database row validation and mapping for set entry."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TypedDict

from core.errors.repository import SetEntryRowError
from schemas.set_entry_schema import SetEntryPublic


class SetEntryRow(TypedDict):
    id: int
    workout_exercise_id: int
    set_number: int
    reps: int
    weight: Decimal
    rpe: int | None
    is_warmup: bool
    completed: bool
    created_at: datetime


def _parse_set_entry_row(row: dict[str, object]) -> SetEntryRow:
    """Validate and normalize a raw database row into a typed SetEntryRow."""
    id_value = row.get("id")
    workout_exercise_id = row.get("workout_exercise_id")
    set_number = row.get("set_number")
    reps = row.get("reps")
    weight = row.get("weight")
    rpe = row.get("rpe")
    is_warmup = row.get("is_warmup")
    completed = row.get("completed")
    created_at = row.get("created_at")

    if not isinstance(id_value, int):
        raise SetEntryRowError.invalid_type("id", "int")
    if not isinstance(workout_exercise_id, int):
        raise SetEntryRowError.invalid_type("workout_exercise_id", "int")
    if not isinstance(set_number, int):
        raise SetEntryRowError.invalid_type("set_number", "int")
    if not isinstance(reps, int):
        raise SetEntryRowError.invalid_type("reps", "int")
    if not isinstance(weight, (Decimal, int, float)):
        raise SetEntryRowError.invalid_type("weight", "numeric")
    if rpe is not None and not isinstance(rpe, int):
        raise SetEntryRowError.invalid_type("rpe", "int | None")
    if not isinstance(is_warmup, bool):
        raise SetEntryRowError.invalid_type("is_warmup", "bool")
    if not isinstance(completed, bool):
        raise SetEntryRowError.invalid_type("completed", "bool")
    if not isinstance(created_at, datetime):
        raise SetEntryRowError.invalid_type("created_at", "datetime")

    return SetEntryRow(
        id=id_value,
        workout_exercise_id=workout_exercise_id,
        set_number=set_number,
        reps=reps,
        weight=Decimal(str(weight)),
        rpe=rpe,
        is_warmup=is_warmup,
        completed=completed,
        created_at=created_at,
    )


def map_set_entry(row: dict[str, object]) -> SetEntryPublic:
    """Convert a raw database row into a validated SetEntryPublic model."""
    set_entry_row = _parse_set_entry_row(row)
    return SetEntryPublic.model_validate(set_entry_row)
