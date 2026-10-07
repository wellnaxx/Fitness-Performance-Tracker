"""Shared database type checks and compatibility across all entity mappers."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest import TestCase

from core.errors.base import RowValidationError
from core.errors.repository import (
    BodyMeasurementRowError,
    BodyWeightEntryRowError,
    ExerciseRowError,
    MealItemRowError,
    MealRowError,
    ProgressPhotoRowError,
    SetEntryRowError,
    UserGoalRowError,
    UserRowError,
    WorkoutExerciseRowError,
    WorkoutRowError,
)
from data.validation import RowValidator
from tests.test_row_mappers import mapper_cases

if TYPE_CHECKING:
    from collections.abc import Callable

NOW = datetime(2026, 10, 7, 12)
TODAY = NOW.date()
ERROR_TYPES: dict[str, type[RowValidationError]] = {
    "user": UserRowError,
    "user_goal": UserGoalRowError,
    "exercise": ExerciseRowError,
    "workout": WorkoutRowError,
    "workout_exercise": WorkoutExerciseRowError,
    "meal": MealRowError,
    "meal_item": MealItemRowError,
    "set_entry": SetEntryRowError,
    "body_weight_entry": BodyWeightEntryRowError,
    "body_measurement": BodyMeasurementRowError,
    "progress_photo": ProgressPhotoRowError,
}


class RowValidatorTests(TestCase):
    def checks(
        self, validator: RowValidator
    ) -> tuple[tuple[Callable[[object, str], object], str, object], ...]:
        return (
            (validator.require_int, "int", 7),
            (validator.require_optional_int, "int | None", 7),
            (validator.require_str, "str", " unchanged "),
            (validator.require_optional_str, "str | None", " unchanged "),
            (validator.require_bool, "bool", True),
            (validator.require_date, "date", TODAY),
            (validator.require_optional_date, "date | None", TODAY),
            (validator.require_datetime, "datetime", NOW),
            (validator.require_optional_datetime, "datetime | None", NOW),
            (validator.require_numeric, "numeric", Decimal("0.100")),
            (validator.require_optional_numeric, "numeric | None", Decimal("0.100")),
        )

    def test_valid_values_are_returned_without_coercion_or_mutation(self) -> None:
        for check, expected, value in self.checks(RowValidator()):
            with self.subTest(expected=expected):
                self.assertIs(check(value, "column"), value)

    def test_invalid_values_preserve_each_entity_error_type_and_field_message(self) -> None:
        for error_type in (RowValidationError, *ERROR_TYPES.values()):
            validator = RowValidator(error_type)
            for check, expected, _ in self.checks(validator):
                with self.subTest(error=error_type.__name__, expected=expected):
                    with self.assertRaises(error_type) as raised:
                        check(object(), "column")
                    self.assertIs(type(raised.exception), error_type)
                    self.assertEqual(str(raised.exception), str(error_type.invalid_type("column", expected)))

    def test_required_values_reject_none_and_optional_values_preserve_none(self) -> None:
        for check, expected, _ in self.checks(RowValidator()):
            with self.subTest(expected=expected):
                if expected.endswith(" | None"):
                    self.assertIsNone(check(None, "column"))
                else:
                    with self.assertRaises(RowValidationError):
                        check(None, "column")

    def test_checks_do_not_parse_or_coerce_strings_numbers_and_dates(self) -> None:
        validator = RowValidator()
        checks = (
            (validator.require_int, "7"),
            (validator.require_int, 7.0),
            (validator.require_str, 7),
            (validator.require_bool, 1),
            (validator.require_bool, "true"),
            (validator.require_date, "2026-10-07"),
            (validator.require_datetime, TODAY),
            (validator.require_datetime, "2026-10-07T12:00:00"),
            (validator.require_numeric, "0.1"),
            (validator.require_optional_numeric, "0.1"),
        )
        for check, value in checks:
            with self.subTest(check=check.__name__, value=value), self.assertRaises(RowValidationError):
                check(value, "column")

    def test_numeric_checks_preserve_all_supported_number_types(self) -> None:
        validator = RowValidator()
        for value in (0, -1, 0.1, Decimal("0.100"), float("inf"), Decimal("NaN")):
            with self.subTest(value=value):
                self.assertIs(validator.require_numeric(value, "column"), value)
                self.assertIs(validator.require_optional_numeric(value, "column"), value)

    def test_existing_integer_and_date_subclass_rules_are_preserved(self) -> None:
        validator = RowValidator()
        self.assertIs(validator.require_int(True, "column"), True)
        self.assertIs(validator.require_optional_int(False, "column"), False)
        self.assertIs(validator.require_date(NOW, "column"), NOW)
        self.assertIs(validator.require_optional_date(NOW, "column"), NOW)

    def test_nullable_decimal_conversion_preserves_float_and_decimal_precision(self) -> None:
        validator = RowValidator(BodyMeasurementRowError)
        self.assertIsNone(validator.require_optional_decimal(None, "waist"))
        for value in (0, 12, 0.1, Decimal("0.100")):
            with self.subTest(value=value):
                self.assertEqual(validator.require_optional_decimal(value, "waist"), Decimal(str(value)))
        invalid_values: tuple[object, ...] = ("0.1", [], {})
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(BodyMeasurementRowError) as raised:
                validator.require_optional_decimal(value, "waist")
            self.assertEqual(
                str(raised.exception), "Invalid body measurement row: 'waist' must be numeric | None"
            )


class MapperValidationCompatibilityTests(TestCase):
    def test_every_column_preserves_entity_error_type_and_expected_type_message(self) -> None:
        integer_fields = {
            "id",
            "user_id",
            "token_version",
            "daily_calorie_target",
            "protein_target",
            "carbs_target",
            "fat_target",
            "weekly_workout_target",
            "workout_id",
            "exercise_id",
            "order_index",
            "set_number",
            "workout_exercise_id",
            "reps",
            "meal_id",
        }
        optional_integer_fields = {"created_by", "rest_seconds", "rpe"}
        numeric_fields = {"target_body_weight", "weight", "calories", "protein", "carbs", "fats"}
        optional_numeric_fields = {
            "serving_size",
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
        }
        date_fields = {"date_of_birth", "start_date", "entry_date", "workout_date"}
        datetime_fields = {"created_at", "updated_at", "eaten_at"}
        bool_fields = {"is_active", "is_compound", "is_custom", "is_warmup", "completed"}
        optional_string_fields = {"description", "equipment", "notes", "profile_picture_url"}
        for case in mapper_cases():
            error_type = ERROR_TYPES[case.entity]
            for field in case.row:
                if field in optional_integer_fields or (field == "user_id" and case.entity == "workout"):
                    expected = "int | None"
                elif field in integer_fields:
                    expected = "int"
                elif field in optional_numeric_fields:
                    expected = "numeric | None"
                elif field in numeric_fields:
                    expected = "numeric"
                elif field in date_fields:
                    expected = "date"
                elif field == "end_date":
                    expected = "date | None"
                elif field in datetime_fields:
                    expected = "datetime"
                elif field in {"started_at", "completed_at"}:
                    expected = "datetime | None"
                elif field in bool_fields:
                    expected = "bool"
                elif field in optional_string_fields:
                    expected = "str | None"
                else:
                    expected = "str"
                # The user fixture includes user_id for shared setup, but it is
                # not a column consumed by the user mapper.
                if case.entity == "user" and field == "user_id":
                    continue
                with self.subTest(entity=case.entity, field=field):
                    with self.assertRaises(error_type) as raised:
                        case.mapper({**case.row, field: object()})
                    self.assertIs(type(raised.exception), error_type)
                    self.assertEqual(str(raised.exception), str(error_type.invalid_type(field, expected)))

    def test_goal_and_measurement_float_conversions_retain_their_distinct_precision_rules(self) -> None:
        cases = {case.entity: case for case in mapper_cases()}
        goal_case = cases["user_goal"]
        measurement_case = cases["body_measurement"]
        goal_result = goal_case.mapper({**goal_case.row, "target_body_weight": 0.1})
        measurement_result = measurement_case.mapper({**measurement_case.row, "waist": 0.1})
        self.assertEqual(goal_result.model_dump()["target_body_weight"], Decimal.from_float(0.1))
        self.assertEqual(measurement_result.model_dump()["waist"], Decimal("0.1"))

    def test_exercise_missing_column_still_precedes_type_validation(self) -> None:
        case = next(case for case in mapper_cases() if case.entity == "exercise")
        row = {**case.row, "id": "invalid"}
        del row["updated_at"]
        with self.assertRaises(KeyError) as raised:
            case.mapper(row)
        self.assertEqual(raised.exception.args, ("updated_at",))

    def test_primary_measurement_fields_are_validated_before_nullable_measurements(self) -> None:
        case = next(case for case in mapper_cases() if case.entity == "body_measurement")
        with self.assertRaises(BodyMeasurementRowError) as raised:
            case.mapper({**case.row, "notes": 42, "waist": "invalid"})
        self.assertEqual(str(raised.exception), "Invalid body measurement row: 'notes' must be str | None")
