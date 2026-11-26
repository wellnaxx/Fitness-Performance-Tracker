"""Shared meal and workout ownership checks before accessing child records."""

import logging
from unittest import TestCase
from unittest.mock import create_autospec, patch

from core.errors.database import DatabaseError
from core.errors.meal import MealNotFoundError
from core.errors.repository import MealRepositoryError, MealRowError, WorkoutRepositoryError
from core.errors.workout import WorkoutNotFoundError
from core.errors.workout_exercise import WorkoutExerciseNotFoundError
from ports.repositories.meal_repository import MealRepositoryPort
from ports.repositories.set_entry_repository import SetEntryRepositoryPort
from ports.repositories.workout_exercise_repository import WorkoutExerciseRepositoryPort
from ports.repositories.workout_repository import WorkoutRepositoryPort
from ports.unit_of_work import UnitOfWorkPort
from schemas.set_entry_schema import SetEntryCreate
from services.ownership import require_owned_meal, require_owned_workout
from services.set_entry_service import SetEntryService
from tests.fixtures import ENTRY_ID, MEAL_ID, USER_ID, WORKOUT_ID, entry, meal, workout


class MealOwnershipTests(TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.repo = create_autospec(MealRepositoryPort, instance=True, spec_set=True)

    def test_owned_meal_is_returned_from_exact_user_scoped_lookup(self) -> None:
        owned = meal()
        self.repo.get_by_user_and_id.return_value = owned
        self.assertIs(require_owned_meal(self.repo, USER_ID, MEAL_ID, logger=self.logger), owned)
        self.repo.get_by_user_and_id.assert_called_once_with(USER_ID, MEAL_ID)

    def test_missing_or_foreign_meal_is_not_found_with_correct_ids_in_warning(self) -> None:
        self.repo.get_by_user_and_id.return_value = None
        for user_id in (USER_ID, USER_ID + 1):
            with self.subTest(user_id=user_id), patch.object(self, "logger") as logger:
                with self.assertRaises(MealNotFoundError) as raised:
                    require_owned_meal(self.repo, user_id, MEAL_ID, logger=self.logger)
                self.assertEqual(str(raised.exception), str(MealNotFoundError.not_accessible(MEAL_ID)))
                self.repo.get_by_user_and_id.assert_called_with(user_id, MEAL_ID)
                logger.warning.assert_called_once_with(
                    "Meal with ID %s not found or not visible to user %s.", MEAL_ID, user_id
                )

    def test_persistence_failures_propagate_without_becoming_not_found(self) -> None:
        for failure in (
            DatabaseError("database error"),
            MealRepositoryError("repository error"),
            MealRowError("row error"),
        ):
            with self.subTest(error=type(failure).__name__):
                self.repo.get_by_user_and_id.side_effect = failure
                with self.assertRaises(type(failure)) as raised:
                    require_owned_meal(self.repo, USER_ID, MEAL_ID, logger=self.logger)
                self.assertIs(raised.exception, failure)


class WorkoutOwnershipTests(TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.repo = create_autospec(WorkoutRepositoryPort, instance=True, spec_set=True)

    def test_owned_workout_is_returned_without_an_unscoped_lookup(self) -> None:
        owned = workout()
        self.repo.get_by_user_and_id.return_value = owned
        self.assertIs(require_owned_workout(self.repo, USER_ID, WORKOUT_ID, logger=self.logger), owned)
        self.repo.get_by_user_and_id.assert_called_once_with(USER_ID, WORKOUT_ID)
        self.repo.get_visible_by_id.assert_not_called()

    def test_missing_or_foreign_workout_raises_existing_access_error(self) -> None:
        self.repo.get_by_user_and_id.return_value = None
        for user_id in (USER_ID, USER_ID + 1):
            with self.subTest(user_id=user_id):
                self.repo.reset_mock()
                with (
                    self.assertLogs(__name__, level="WARNING"),
                    self.assertRaises(WorkoutNotFoundError) as raised,
                ):
                    require_owned_workout(self.repo, user_id, WORKOUT_ID, logger=self.logger)
                self.assertEqual(str(raised.exception), str(WorkoutNotFoundError.not_accessible(WORKOUT_ID)))
                self.repo.get_by_user_and_id.assert_called_once_with(user_id, WORKOUT_ID)

    def test_repository_failure_propagates_without_becoming_not_found(self) -> None:
        failure = WorkoutRepositoryError("database unavailable")
        self.repo.get_by_user_and_id.side_effect = failure
        with self.assertRaises(WorkoutRepositoryError) as raised:
            require_owned_workout(self.repo, USER_ID, WORKOUT_ID, logger=self.logger)
        self.assertIs(raised.exception, failure)


class SetEntryOwnershipTests(TestCase):
    def setUp(self) -> None:
        self.sets = create_autospec(SetEntryRepositoryPort, instance=True, spec_set=True)
        self.exercises = create_autospec(WorkoutExerciseRepositoryPort, instance=True, spec_set=True)
        self.workouts = create_autospec(WorkoutRepositoryPort, instance=True, spec_set=True)
        self.uow = create_autospec(UnitOfWorkPort, instance=True, spec_set=True)
        self.service = SetEntryService(self.sets, self.exercises, self.workouts, self.uow)
        self.data = SetEntryCreate(workout_exercise_id=ENTRY_ID, set_number=1, reps=0, weight=0)

    def test_missing_workout_exercise_blocks_workout_lookup_and_writes(self) -> None:
        self.exercises.get_by_id.return_value = None
        with self.assertRaises(WorkoutExerciseNotFoundError):
            self.service.create(USER_ID, self.data)
        self.exercises.get_by_id.assert_called_once_with(ENTRY_ID)
        self.assertEqual(self.workouts.mock_calls, [])
        self.assertEqual(self.sets.mock_calls, [])
        self.uow.__enter__.assert_not_called()

    def test_inaccessible_parent_workout_blocks_writes(self) -> None:
        self.exercises.get_by_id.return_value = entry()
        self.workouts.get_by_user_and_id.return_value = None
        with (
            self.assertLogs("services.set_entry_service", level="WARNING"),
            self.assertRaises(WorkoutNotFoundError),
        ):
            self.service.create(USER_ID, self.data)
        self.exercises.get_by_id.assert_called_once_with(ENTRY_ID)
        self.workouts.get_by_user_and_id.assert_called_once_with(USER_ID, WORKOUT_ID)
        self.assertEqual(self.sets.mock_calls, [])
        self.uow.__enter__.assert_not_called()
