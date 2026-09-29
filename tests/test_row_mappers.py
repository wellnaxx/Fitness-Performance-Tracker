"""Regression coverage for database row validation and repository mapping."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from importlib import import_module
from unittest import TestCase
from unittest.mock import patch

from pydantic import BaseModel, ValidationError

from core.errors.base import RowValidationError
from data.mappers.body_measurement import map_body_measurement
from data.mappers.body_weight_entry import map_body_weight_entry
from data.mappers.exercise import map_exercise
from data.mappers.meal import map_meal
from data.mappers.meal_item import map_meal_item
from data.mappers.progress_photo import map_progress_photo
from data.mappers.set_entry import map_set_entry
from data.mappers.user import map_user
from data.mappers.user_goal import map_user_goal
from data.mappers.workout import map_workout
from data.mappers.workout_exercise import map_workout_exercise

NOW = datetime(2026, 9, 29, 12)
TODAY = date(2026, 9, 29)


@dataclass(frozen=True)
class MapperCase:
    entity: str
    mapper: Callable[[dict[str, object]], BaseModel]
    model_name: str
    row: dict[str, object]


def mapper_cases() -> tuple[MapperCase, ...]:
    """Return independent database rows, including nullable and numeric columns."""
    owned: dict[str, object] = {"id": 17, "user_id": 7}
    timestamps: dict[str, object] = {"created_at": NOW, "updated_at": NOW}
    return (
        MapperCase(
            "user",
            map_user,
            "UserInternal",
            {
                **owned,
                **timestamps,
                "username": "test_user",
                "first_name": "Test",
                "last_name": "User",
                "date_of_birth": date(2000, 1, 1),
                "email": "test@example.com",
                "password_hash": "stored-hash",
                "profile_picture_url": None,
                "token_version": 2,
                "weight_unit_preference": "kg",
                "measurement_unit_preference": "cm",
            },
        ),
        MapperCase(
            "user_goal",
            map_user_goal,
            "UserGoalPublic",
            {
                **owned,
                "daily_calorie_target": 2000,
                "protein_target": 150,
                "carbs_target": 200,
                "fat_target": 60,
                "weekly_workout_target": 3,
                "target_body_weight": Decimal("75.5"),
                "start_date": TODAY,
                "end_date": None,
                "is_active": True,
            },
        ),
        MapperCase(
            "exercise",
            map_exercise,
            "ExercisePublic",
            {
                "id": 17,
                **timestamps,
                "name": "Squat",
                "description": None,
                "muscle_group": "legs",
                "equipment": None,
                "is_compound": True,
                "created_by": None,
                "is_custom": False,
            },
        ),
        MapperCase(
            "workout",
            map_workout,
            "WorkoutPublic",
            {
                **owned,
                **timestamps,
                "user_id": None,
                "name": "Template",
                "description": None,
                "workout_date": TODAY,
                "started_at": None,
                "completed_at": None,
                "notes": None,
            },
        ),
        MapperCase(
            "workout_exercise",
            map_workout_exercise,
            "WorkoutExercisePublic",
            {
                "id": 17,
                "workout_id": 11,
                "exercise_id": 9,
                "order_index": 0,
                "rest_seconds": None,
                "notes": None,
            },
        ),
        MapperCase(
            "set_entry",
            map_set_entry,
            "SetEntryPublic",
            {
                "id": 17,
                "workout_exercise_id": 11,
                "set_number": 1,
                "reps": 10,
                "weight": Decimal("50.5"),
                "rpe": None,
                "is_warmup": False,
                "completed": True,
                "created_at": NOW,
            },
        ),
        MapperCase(
            "meal",
            map_meal,
            "MealPublic",
            {
                **owned,
                **timestamps,
                "name": "Lunch",
                "description": None,
                "eaten_at": NOW,
                "meal_type": "lunch",
                "notes": None,
            },
        ),
        MapperCase(
            "meal_item",
            map_meal_item,
            "MealItemPublic",
            {
                "id": 17,
                "meal_id": 11,
                "name": "Rice",
                "serving_size": None,
                "calories": Decimal("200.5"),
                "protein": Decimal("5"),
                "carbs": Decimal("40"),
                "fats": Decimal("1"),
                "created_at": NOW,
            },
        ),
        MapperCase(
            "body_weight_entry",
            map_body_weight_entry,
            "BodyWeightEntryPublic",
            {
                **owned,
                "weight": Decimal("75.5"),
                "entry_date": TODAY,
                "created_at": NOW,
            },
        ),
        MapperCase(
            "body_measurement",
            map_body_measurement,
            "BodyMeasurementPublic",
            {
                **owned,
                **timestamps,
                "entry_date": TODAY,
                "waist": Decimal("80.5"),
                "notes": None,
            },
        ),
        MapperCase(
            "progress_photo",
            map_progress_photo,
            "ProgressPhotoPublic",
            {
                **owned,
                "photo_url": "https://example.com/photo.jpg",
                "entry_date": TODAY,
                "notes": None,
                "created_at": NOW,
            },
        ),
    )


class RowMapperTests(TestCase):
    def test_valid_rows_produce_models_without_mutating_input(self) -> None:
        for case in mapper_cases():
            with self.subTest(entity=case.entity):
                original = case.row.copy()
                model = case.mapper(case.row)
                self.assertEqual(type(model).__name__, case.model_name)
                self.assertEqual(model.model_dump()["id"], 17)
                self.assertEqual(case.row, original)
                for field, value in case.row.items():
                    if value is None:
                        self.assertIsNone(model.model_dump()[field])

    def test_invalid_ids_raise_existing_row_errors(self) -> None:
        for case in mapper_cases():
            with self.subTest(entity=case.entity):
                with self.assertRaises(RowValidationError) as error:
                    case.mapper({**case.row, "id": "17"})
                self.assertIn("'id' must be int", str(error.exception))

    def test_missing_required_columns_preserve_error_behavior(self) -> None:
        for case in mapper_cases():
            with self.subTest(entity=case.entity):
                row = case.row.copy()
                del row["id"]
                expected = KeyError if case.entity == "exercise" else RowValidationError
                with self.assertRaises(expected):
                    case.mapper(row)

    def test_numeric_values_preserve_schema_output_types(self) -> None:
        numeric_fields: dict[str, tuple[str, ...]] = {
            "user_goal": ("target_body_weight",),
            "set_entry": ("weight",),
            "meal_item": ("serving_size", "calories", "protein", "carbs", "fats"),
            "body_weight_entry": ("weight",),
            "body_measurement": ("neck", "waist", "left_bicep", "right_calf"),
        }
        for case in mapper_cases():
            for field in numeric_fields.get(case.entity, ()):
                for value in (12, 12.25, Decimal("12.250")):
                    with self.subTest(entity=case.entity, field=field, value=value):
                        result = case.mapper({**case.row, field: value}).model_dump()[field]
                        if case.entity == "set_entry":
                            self.assertIsInstance(result, float)
                            self.assertEqual(result, float(value))
                        else:
                            self.assertIsInstance(result, Decimal)
                            self.assertEqual(result, Decimal(str(value)))

    def test_numeric_strings_are_rejected_before_pydantic_can_coerce_them(self) -> None:
        fields = {
            "user_goal": "target_body_weight",
            "set_entry": "weight",
            "meal_item": "calories",
            "body_weight_entry": "weight",
            "body_measurement": "waist",
        }
        for case in mapper_cases():
            if case.entity in fields:
                with self.subTest(entity=case.entity), self.assertRaises(RowValidationError):
                    case.mapper({**case.row, fields[case.entity]: "12.5"})

    def test_pydantic_constraints_are_still_applied_after_row_validation(self) -> None:
        case = next(case for case in mapper_cases() if case.entity == "body_weight_entry")
        with self.assertRaises(ValidationError):
            case.mapper({**case.row, "weight": Decimal("-1")})

    def test_user_password_hash_and_token_version_are_preserved(self) -> None:
        case = next(case for case in mapper_cases() if case.entity == "user")
        user = map_user(case.row)
        self.assertEqual(user.password_hash, "stored-hash")
        self.assertEqual(user.token_version, 2)

    def test_every_repository_maps_found_rows_and_preserves_missing_results(self) -> None:
        for case in mapper_cases():
            entity = "user_goals" if case.entity == "user_goal" else case.entity
            module = import_module(f"repositories.{entity}_repository")
            class_name = "".join(part.capitalize() for part in entity.split("_")) + "Repository"
            repository = getattr(module, class_name)()
            with self.subTest(entity=case.entity):
                with patch.object(module, "fetch_one", return_value=case.row):
                    self.assertEqual(repository.get_by_id(17), case.mapper(case.row))
                with patch.object(module, "fetch_one", return_value=None):
                    self.assertIsNone(repository.get_by_id(17))
