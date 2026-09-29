"""Database row validation and mapping for workout exercise."""

from __future__ import annotations

from typing import TypedDict

from core.errors.repository import WorkoutExerciseRowError
from schemas.workout_exercises_schema import WorkoutExercisePublic


class WorkoutExerciseRow(TypedDict):
    id: int
    workout_id: int
    exercise_id: int
    order_index: int
    rest_seconds: int | None
    notes: str | None


def _parse_workout_exercise_row(row: dict[str, object]) -> WorkoutExerciseRow:
    """Validate and normalize a raw database row into a typed WorkoutExerciseRow."""
    id_value = row.get("id")
    workout_id = row.get("workout_id")
    exercise_id = row.get("exercise_id")
    order_index = row.get("order_index")
    rest_seconds = row.get("rest_seconds")
    notes = row.get("notes")

    if not isinstance(id_value, int):
        raise WorkoutExerciseRowError.invalid_type("id", "int")
    if not isinstance(workout_id, int):
        raise WorkoutExerciseRowError.invalid_type("workout_id", "int")
    if not isinstance(exercise_id, int):
        raise WorkoutExerciseRowError.invalid_type("exercise_id", "int")
    if not isinstance(order_index, int):
        raise WorkoutExerciseRowError.invalid_type("order_index", "int")
    if rest_seconds is not None and not isinstance(rest_seconds, int):
        raise WorkoutExerciseRowError.invalid_type("rest_seconds", "int | None")
    if notes is not None and not isinstance(notes, str):
        raise WorkoutExerciseRowError.invalid_type("notes", "str | None")

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
