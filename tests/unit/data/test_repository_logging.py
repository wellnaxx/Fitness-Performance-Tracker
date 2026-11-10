"""Repository anomalies have context without logging payloads or normal misses."""

from contextlib import ExitStack
from decimal import Decimal
from importlib import import_module
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from core.errors.base import RepositoryError
from repositories.body_measurement_repository import BodyMeasurementRepository
from schemas.body_measurement_schema import BodyMeasurementCreate
from tests.fixtures import TODAY, USER_ID
from tests.unit.data.test_row_mappers import mapper_cases

# Module, repository class, scoped update method, positional IDs.
REPOSITORIES = (
    ("body_measurement_repository", "BodyMeasurementRepository", "update_owned", (7, 17)),
    ("body_weight_entry_repository", "BodyWeightEntryRepository", "update_owned", (7, 17)),
    ("exercise_repository", "ExerciseRepository", "update_owned", (7, 17)),
    ("meal_repository", "MealRepository", "update_owned", (7, 17)),
    ("meal_item_repository", "MealItemRepository", "update_in_meal", (11, 17)),
    ("progress_photo_repository", "ProgressPhotoRepository", "update_owned", (7, 17)),
    ("set_entry_repository", "SetEntryRepository", "update_in_workout_exercise", (11, 17)),
    ("user_goals_repository", "UserGoalsRepository", "update", (17,)),
    ("user_repository", "UserRepository", "update", (7,)),
    ("workout_repository", "WorkoutRepository", "update_owned", (7, 17)),
    ("workout_exercise_repository", "WorkoutExerciseRepository", "update", (11, 17)),
)


class RepositoryLoggingTests(TestCase):
    def test_all_repositories_reject_unknown_fields_without_logging_field_names_or_values(self) -> None:
        workout_exercise_row = next(case.row for case in mapper_cases() if case.entity == "workout_exercise")
        for name, class_name, method, ids in REPOSITORIES:
            module = import_module(f"repositories.{name}")
            repository = getattr(module, class_name)()
            data = Mock()
            data.model_dump.return_value = {"private-field": "private-value"}
            with self.subTest(repository=name), ExitStack() as stack:
                if name == "workout_exercise_repository":
                    stack.enter_context(patch.object(module, "transaction_cursor", return_value=MagicMock()))
                    stack.enter_context(patch.object(module, "fetch_one_tx", return_value=workout_exercise_row))
                logs = stack.enter_context(self.assertLogs(f"repositories.{name}", level="WARNING"))
                with self.assertRaises(RepositoryError):
                    if name == "user_repository":
                        repository.update(ids[0], **data.model_dump())
                    else:
                        getattr(repository, method)(*ids, data)
                self.assertEqual(len(logs.records), 1)
                self.assertIn("field_count=1", logs.output[0])
                self.assertNotIn("private", logs.output[0])

    def test_normal_missing_rows_do_not_emit_warnings(self) -> None:
        for name, class_name, _method, _ids in REPOSITORIES:
            module = import_module(f"repositories.{name}")
            executor = getattr(module, "default_executor", module)
            with (
                self.subTest(repository=name),
                patch.object(executor, "fetch_one", return_value=None),
                self.assertNoLogs(f"repositories.{name}", level="WARNING"),
            ):
                self.assertIsNone(getattr(module, class_name)().get_by_id(17))

    def test_insert_readback_failure_logs_only_the_assigned_id(self) -> None:
        data = BodyMeasurementCreate(entry_date=TODAY, waist=Decimal("85.123"), notes="private notes")
        with (
            patch("repositories.body_measurement_repository.execute_insert", return_value=37),
            patch.object(BodyMeasurementRepository, "get_by_id", return_value=None),
            self.assertLogs("repositories.body_measurement_repository", level="WARNING") as logs,
            self.assertRaises(RepositoryError),
        ):
            BodyMeasurementRepository().create(USER_ID, data)
        self.assertEqual(len(logs.records), 1)
        self.assertIn("entity_id=37", logs.output[0])
        self.assertNotIn("85.123", logs.output[0])
        self.assertNotIn("private notes", logs.output[0])
