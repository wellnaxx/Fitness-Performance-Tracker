"""Database row validation and mapping for set entry."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

from core.errors.repository import SetEntryRowError
from data.validation import RowValidator
from schemas.set_entry_schema import SetEntryPublic

if TYPE_CHECKING:
    from datetime import datetime

_validator = RowValidator(SetEntryRowError)


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

    id_value = _validator.require_int(row.get("id"), "id")
    workout_exercise_id = _validator.require_int(row.get("workout_exercise_id"), "workout_exercise_id")
    set_number = _validator.require_int(row.get("set_number"), "set_number")
    reps = _validator.require_int(row.get("reps"), "reps")
    weight = _validator.require_numeric(row.get("weight"), "weight")
    rpe = _validator.require_optional_int(row.get("rpe"), "rpe")
    is_warmup = _validator.require_bool(row.get("is_warmup"), "is_warmup")
    completed = _validator.require_bool(row.get("completed"), "completed")
    created_at = _validator.require_datetime(row.get("created_at"), "created_at")

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
