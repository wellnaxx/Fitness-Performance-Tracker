"""Database row validation and mapping for workout exercise."""

from __future__ import annotations

from typing import TypedDict

from core.errors.repository import WorkoutExerciseRowError
from data.validation import RowValidator
from schemas.workout_exercises_schema import WorkoutExercisePublic

_validator = RowValidator(WorkoutExerciseRowError)


class WorkoutExerciseRow(TypedDict):
    id: int
    workout_id: int
    exercise_id: int
    order_index: int
    rest_seconds: int | None
    notes: str | None


def _parse_workout_exercise_row(row: dict[str, object]) -> WorkoutExerciseRow:
    """Validate and normalize a raw database row into a typed WorkoutExerciseRow."""

    id_value = _validator.require_int(row.get("id"), "id")
    workout_id = _validator.require_int(row.get("workout_id"), "workout_id")
    exercise_id = _validator.require_int(row.get("exercise_id"), "exercise_id")
    order_index = _validator.require_int(row.get("order_index"), "order_index")
    rest_seconds = _validator.require_optional_int(row.get("rest_seconds"), "rest_seconds")
    notes = _validator.require_optional_str(row.get("notes"), "notes")

    return WorkoutExerciseRow(
        id=id_value,
        workout_id=workout_id,
        exercise_id=exercise_id,
        order_index=order_index,
        rest_seconds=rest_seconds,
        notes=notes,
    )


def map_workout_exercise(
    row: dict[str, object],
) -> WorkoutExercisePublic:
    """Convert a raw database row into a validated WorkoutExercisePublic model."""
    workout_exercise_row = _parse_workout_exercise_row(row)
    return WorkoutExercisePublic.model_validate(workout_exercise_row)
