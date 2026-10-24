"""Request boundaries for every entity, including fields rejected before service calls."""

import unittest
from datetime import timedelta
from decimal import Decimal

from pydantic import BaseModel, ValidationError

from schemas.body_measurement_schema import BodyMeasurementCreate, BodyMeasurementUpdate
from schemas.body_weight_entry_schema import BodyWeightEntryCreate, BodyWeightEntryUpdate
from schemas.exercise_schema import ExerciseCreate, ExerciseUpdate
from schemas.meal_item_schema import MealItemCreate, MealItemUpdate
from schemas.meal_schema import MealCreate, MealUpdate
from schemas.progress_photo_schema import ProgressPhotoCreate, ProgressPhotoUpdate
from schemas.set_entry_schema import SetEntryCreate, SetEntryUpdate
from schemas.user_goals_schema import UserGoalCreate, UserGoalUpdate
from schemas.user_schema import (
    ChangeUserPassword,
    ProfilePictureUpdate,
    UserCreate,
    UserPreferencesUpdate,
    UserUpdate,
)
from schemas.workout_exercises_schema import WorkoutExerciseCreate, WorkoutExerciseUpdate
from schemas.workout_schema import WorkoutCreate, WorkoutUpdate
from tests.fixtures import NOW, TODAY, exercise, goal, meal, user, workout


def create_cases() -> tuple[tuple[type[BaseModel], dict[str, object]], ...]:
    return (
        (UserCreate, {**user().model_dump(), "password": "Strong123!"}),
        (UserGoalCreate, goal().model_dump()),
        (ExerciseCreate, exercise().model_dump()),
        (WorkoutCreate, workout().model_dump()),
        (WorkoutExerciseCreate, {"exercise_id": 13, "order_index": 0}),
        (MealCreate, meal().model_dump()),
        (MealItemCreate, {"meal_id": 23, "name": "Rice", "calories": 0, "protein": 0, "carbs": 0, "fats": 0}),
        (SetEntryCreate, {"workout_exercise_id": 17, "set_number": 1, "reps": 0, "weight": 0}),
        (BodyWeightEntryCreate, {"entry_date": TODAY, "weight": "75.5"}),
        (BodyMeasurementCreate, {"entry_date": TODAY, "waist": "80.5"}),
        (ProgressPhotoCreate, {"entry_date": TODAY, "photo_url": "https://example.com/photo.jpg"}),
    )


class SchemaValidationTests(unittest.TestCase):
    def test_each_entity_accepts_valid_creation_data(self) -> None:
        for schema, data in create_cases():
            with self.subTest(schema=schema.__name__):
                result = schema.model_validate(data)
                self.assertIsInstance(result, schema)

    def test_each_required_creation_field_cannot_be_omitted_or_null(self) -> None:
        for schema, data in create_cases():
            for field, info in schema.model_fields.items():
                if not info.is_required():
                    continue
                for missing in (True, False):
                    with self.subTest(schema=schema.__name__, field=field, missing=missing):
                        invalid = dict(data)
                        if missing:
                            invalid.pop(field, None)
                        else:
                            invalid[field] = None
                        with self.assertRaises(ValidationError):
                            schema.model_validate(invalid)

    def test_all_update_schemas_accept_empty_and_explicit_null_fields(self) -> None:
        schemas = (
            UserUpdate,
            UserGoalUpdate,
            ExerciseUpdate,
            WorkoutUpdate,
            WorkoutExerciseUpdate,
            MealUpdate,
            MealItemUpdate,
            SetEntryUpdate,
            BodyWeightEntryUpdate,
            BodyMeasurementUpdate,
            ProgressPhotoUpdate,
            UserPreferencesUpdate,
            ProfilePictureUpdate,
        )
        for schema in schemas:
            with self.subTest(schema=schema.__name__):
                self.assertEqual(schema.model_validate({}).model_dump(exclude_unset=True), {})
                nulls = dict.fromkeys(schema.model_fields)
                self.assertEqual(schema.model_validate(nulls).model_dump(exclude_none=True), {})

    def test_names_and_optional_text_enforce_length_limits(self) -> None:
        cases = (
            (
                ExerciseCreate,
                ExerciseUpdate,
                exercise().model_dump(),
                {"name": 100, "description": 500, "muscle_group": 50, "equipment": 50},
            ),
            (
                WorkoutCreate,
                WorkoutUpdate,
                workout().model_dump(),
                {"name": 100, "description": 500, "notes": 1000},
            ),
            (MealCreate, MealUpdate, meal().model_dump(), {"name": 100, "description": 500, "notes": 500}),
            (
                WorkoutExerciseCreate,
                WorkoutExerciseUpdate,
                {"exercise_id": 13, "order_index": 0},
                {"notes": 500},
            ),
            (
                MealItemCreate,
                MealItemUpdate,
                {"meal_id": 23, "name": "Rice", "calories": 0, "protein": 0, "carbs": 0, "fats": 0},
                {"name": 100},
            ),
            (
                ProgressPhotoCreate,
                ProgressPhotoUpdate,
                {"entry_date": TODAY, "photo_url": "https://example.com/p.jpg"},
                {"notes": 1000},
            ),
        )
        for create_schema, update_schema, data, limits in cases:
            for schema, base in ((create_schema, data), (update_schema, {})):
                for field, maximum in limits.items():
                    with self.subTest(schema=schema.__name__, field=field):
                        schema.model_validate({**base, field: "x" * maximum})
                        with self.assertRaises(ValidationError):
                            schema.model_validate({**base, field: "x" * (maximum + 1)})
                        if field == "name":
                            schema.model_validate({**base, field: "x"})
                            with self.assertRaises(ValidationError):
                                schema.model_validate({**base, field: ""})

    def test_registration_username_password_and_name_boundaries(self) -> None:
        data = {**user().model_dump(), "password": "Strong123!"}
        for field, minimum, maximum in (
            ("username", 2, 16),
            ("first_name", 2, 32),
            ("last_name", 2, 32),
            ("password", 8, 64),
        ):
            for length, valid in ((minimum - 1, False), (minimum, True), (maximum, True), (maximum + 1, False)):
                with self.subTest(field=field, length=length):
                    value = "Aa1!" + "x" * (length - 4) if field == "password" else "x" * length
                    payload = {**data, field: value}
                    if valid:
                        UserCreate.model_validate(payload)
                    else:
                        with self.assertRaises(ValidationError):
                            UserCreate.model_validate(payload)

    def test_registration_and_password_change_reject_each_missing_strength_requirement(self) -> None:
        for password in ("lowercase1!", "UPPERCASE1!", "NoDigitsHere!", "NoSpecial123", ""):
            for schema, base in (
                (UserCreate, {**user().model_dump()}),
                (ChangeUserPassword, {"old_password": "Original123!"}),
            ):
                field = "password" if schema is UserCreate else "new_password"
                with (
                    self.subTest(schema=schema.__name__, password=password),
                    self.assertRaises(ValidationError),
                ):
                    schema.model_validate({**base, field: password})

    def test_email_validation_applies_to_registration_and_profile_updates(self) -> None:
        for invalid in ("not-an-email", "user@", "@example.com"):
            for schema, base in (
                (UserCreate, {**user().model_dump(), "password": "Strong123!"}),
                (UserUpdate, {}),
            ):
                with self.subTest(schema=schema.__name__, email=invalid), self.assertRaises(ValidationError):
                    schema.model_validate({**base, "email": invalid})

    def test_goal_date_range_allows_equal_dates_and_open_end_but_rejects_reversed_dates(self) -> None:
        for schema in (UserGoalCreate, UserGoalUpdate):
            for end, valid in (
                (None, True),
                (TODAY, True),
                (TODAY + timedelta(days=1), True),
                (TODAY - timedelta(days=1), False),
            ):
                with self.subTest(schema=schema.__name__, end=end):
                    data = {**goal().model_dump(), "start_date": TODAY, "end_date": end}
                    if valid:
                        schema.model_validate(data)
                    else:
                        with self.assertRaises(ValidationError):
                            schema.model_validate(data)

    def test_workout_time_range_allows_equal_or_missing_times_but_rejects_reversed_times(self) -> None:
        for schema in (WorkoutCreate, WorkoutUpdate):
            for start, end, valid in (
                (None, None, True),
                (NOW, None, True),
                (None, NOW, True),
                (NOW, NOW, True),
                (NOW, NOW + timedelta(seconds=1), True),
                (NOW, NOW - timedelta(seconds=1), False),
            ):
                with self.subTest(schema=schema.__name__, start=start, end=end):
                    data = {**workout().model_dump(), "started_at": start, "completed_at": end}
                    if valid:
                        schema.model_validate(data)
                    else:
                        with self.assertRaises(ValidationError):
                            schema.model_validate(data)

    def test_nonnegative_fields_accept_zero_and_reject_negative_values(self) -> None:
        cases: tuple[tuple[type[BaseModel], dict[str, object], tuple[str, ...]], ...] = (
            (WorkoutExerciseCreate, {"exercise_id": 13, "order_index": 0}, ("order_index", "rest_seconds")),
            (WorkoutExerciseUpdate, {}, ("order_index", "rest_seconds")),
            (
                SetEntryCreate,
                {"workout_exercise_id": 17, "set_number": 1, "reps": 0, "weight": 0},
                ("reps", "weight"),
            ),
            (SetEntryUpdate, {}, ("reps", "weight")),
            (
                MealItemCreate,
                {"meal_id": 23, "name": "Rice", "calories": 0, "protein": 0, "carbs": 0, "fats": 0},
                ("serving_size", "calories", "protein", "carbs", "fats"),
            ),
            (MealItemUpdate, {}, ("serving_size", "calories", "protein", "carbs", "fats")),
            (
                UserGoalCreate,
                goal().model_dump(),
                (
                    "daily_calorie_target",
                    "protein_target",
                    "carbs_target",
                    "fat_target",
                    "weekly_workout_target",
                ),
            ),
            (UserGoalUpdate, {}, ("protein_target", "carbs_target", "fat_target", "weekly_workout_target")),
        )
        for schema, base, fields in cases:
            for field in fields:
                with self.subTest(schema=schema.__name__, field=field):
                    self.assertEqual(schema.model_validate({**base, field: 0}).model_dump()[field], 0)
                    with self.assertRaises(ValidationError):
                        schema.model_validate({**base, field: -1})

    def test_positive_fields_reject_zero_and_negative_values(self) -> None:
        cases: tuple[tuple[type[BaseModel], dict[str, object], str], ...] = (
            (BodyWeightEntryCreate, {"entry_date": TODAY}, "weight"),
            (BodyWeightEntryUpdate, {}, "weight"),
            (UserGoalCreate, goal().model_dump(), "target_body_weight"),
            (UserGoalUpdate, {}, "target_body_weight"),
            (UserGoalUpdate, {}, "daily_calorie_target"),
            (SetEntryCreate, {"workout_exercise_id": 17, "reps": 0, "weight": 0}, "set_number"),
            (SetEntryUpdate, {}, "set_number"),
        )
        for schema, base, field in cases:
            with self.subTest(schema=schema.__name__, field=field):
                self.assertEqual(schema.model_validate({**base, field: 1}).model_dump()[field], 1)
                for invalid in (-1, 0):
                    with self.assertRaises(ValidationError):
                        schema.model_validate({**base, field: invalid})

    def test_rpe_accepts_one_through_ten_and_optional_none(self) -> None:
        for schema, base in (
            (SetEntryCreate, {"workout_exercise_id": 17, "set_number": 1, "reps": 0, "weight": 0}),
            (SetEntryUpdate, {}),
        ):
            for value in (None, 1, 10, 0, 11):
                with self.subTest(schema=schema.__name__, rpe=value):
                    if value in (0, 11):
                        with self.assertRaises(ValidationError):
                            schema.model_validate({**base, "rpe": value})
                    else:
                        self.assertEqual(
                            schema.model_validate({**base, "rpe": value}).model_dump()["rpe"], value
                        )

    def test_body_measurement_requires_at_least_one_positive_measurement(self) -> None:
        fields = (
            "neck",
            "shoulders",
            "waist",
            "chest",
            "hips",
            "left_bicep",
            "right_bicep",
            "left_forearm",
            "right_forearm",
            "left_thigh",
            "right_thigh",
            "left_calf",
            "right_calf",
        )
        for data in (
            {"entry_date": TODAY},
            {"entry_date": TODAY, "notes": "No measurements"},
            {"entry_date": TODAY, **dict.fromkeys(fields)},
        ):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                BodyMeasurementCreate.model_validate(data)
        for field in fields:
            for schema in (BodyMeasurementCreate, BodyMeasurementUpdate):
                with self.subTest(schema=schema.__name__, field=field):
                    result = schema.model_validate({"entry_date": TODAY, field: "0.1"})
                    self.assertEqual(result.model_dump()[field], Decimal("0.1"))
                    for invalid in (0, -1):
                        with self.assertRaises(ValidationError):
                            schema.model_validate({"entry_date": TODAY, field: invalid})

    def test_photo_urls_require_http_or_https(self) -> None:
        for schema, field, base in (
            (ProfilePictureUpdate, "profile_picture_url", {}),
            (ProgressPhotoCreate, "photo_url", {"entry_date": TODAY}),
            (ProgressPhotoUpdate, "photo_url", {}),
        ):
            for url in (
                "http://example.com/a.jpg",
                "https://example.com/a.jpg",
                "ftp://example.com/a.jpg",
                "bad",
            ):
                with self.subTest(schema=schema.__name__, url=url):
                    if url.startswith("http"):
                        self.assertEqual(
                            str(schema.model_validate({**base, field: url}).model_dump()[field]), url
                        )
                    else:
                        with self.assertRaises(ValidationError):
                            schema.model_validate({**base, field: url})

    def test_preferences_normalize_all_supported_units_and_reject_others(self) -> None:
        for field, allowed in (
            ("weight_unit_preference", ("kg", "lb")),
            ("measurement_unit_preference", ("cm", "in")),
        ):
            for unit in allowed:
                with self.subTest(field=field, unit=unit):
                    result = UserPreferencesUpdate.model_validate({field: f" {unit.upper()} "})
                    self.assertEqual(result.model_dump()[field], unit)
            for invalid in ("", "stones", "meters"):
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValidationError):
                    UserPreferencesUpdate.model_validate({field: invalid})

    def test_meal_types_normalize_in_create_and_update_requests(self) -> None:
        for schema, base in ((MealCreate, meal().model_dump()), (MealUpdate, {})):
            for meal_type in ("breakfast", "lunch", "dinner", "snack"):
                with self.subTest(schema=schema.__name__, meal_type=meal_type):
                    result = schema.model_validate({**base, "meal_type": f" {meal_type.upper()} "})
                    self.assertEqual(result.model_dump()["meal_type"], meal_type)
            for invalid in ("", "brunch"):
                with self.subTest(schema=schema.__name__, invalid=invalid), self.assertRaises(ValidationError):
                    schema.model_validate({**base, "meal_type": invalid})
