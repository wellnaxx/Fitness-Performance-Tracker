from __future__ import annotations

from core.errors.base import RepositoryError, RowValidationError


def _repo_error(name: str, entity: str) -> type[RepositoryError]:
    """Create a RepositoryError subclass with the given entity_name."""
    return type(name, (RepositoryError,), {"entity_name": entity})


def _row_error(name: str, row: str) -> type[RowValidationError]:
    """Create a RowValidationError subclass with the given row_name."""
    return type(name, (RowValidationError,), {"row_name": row})


WorkoutRepositoryError = _repo_error("WorkoutRepositoryError", "Workout")
WorkoutRowError = _row_error("WorkoutRowError", "workout")

ExerciseRepositoryError = _repo_error("ExerciseRepositoryError", "Exercise")
ExerciseRowError = _row_error("ExerciseRowError", "exercise")

MealRepositoryError = _repo_error("MealRepositoryError", "Meal")
MealRowError = _row_error("MealRowError", "meal")

MealItemRepositoryError = _repo_error("MealItemRepositoryError", "Meal item")
MealItemRowError = _row_error("MealItemRowError", "meal item")

ProgressPhotoRepositoryError = _repo_error("ProgressPhotoRepositoryError", "Progress photo")
ProgressPhotoRowError = _row_error("ProgressPhotoRowError", "progress photo")

SetEntryRepositoryError = _repo_error("SetEntryRepositoryError", "Set entry")
SetEntryRowError = _row_error("SetEntryRowError", "set entry")

UserRepositoryError = _repo_error("UserRepositoryError", "User")
UserRowError = _row_error("UserRowError", "user")

BodyWeightEntryRepositoryError = _repo_error("BodyWeightEntryRepositoryError", "Body weight entry")
BodyWeightEntryRowError = _row_error("BodyWeightEntryRowError", "body weight entry")

BodyMeasurementRepositoryError = _repo_error("BodyMeasurementRepositoryError", "Body measurement")
BodyMeasurementRowError = _row_error("BodyMeasurementRowError", "body measurement")

UserGoalsRepositoryError = _repo_error("UserGoalsRepositoryError", "Goal")
UserGoalRowError = _row_error("UserGoalRowError", "user goal")

WorkoutExerciseRepositoryError = _repo_error("WorkoutExerciseRepositoryError", "Workout exercise")
WorkoutExerciseRowError = _row_error("WorkoutExerciseRowError", "workout exercise")
