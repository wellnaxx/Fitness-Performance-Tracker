"""Visible-name uniqueness and custom exercise ownership rules."""

import unittest
from unittest.mock import create_autospec

from core.errors.exercise import (
    ExerciseCreationError,
    ExerciseDeleteError,
    ExerciseNameAlreadyExistsError,
    ExerciseNotFoundError,
    ExerciseUpdateError,
)
from core.errors.repository import ExerciseRepositoryError
from ports.repositories.exercise_repository import ExerciseRepositoryPort
from schemas.exercise_schema import ExerciseCreate, ExerciseUpdate
from services.exercise_service import ExerciseService
from tests.fixtures import EXERCISE_ID, USER_ID, exercise


class ExerciseServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = create_autospec(ExerciseRepositoryPort, instance=True, spec_set=True)
        self.service = ExerciseService(self.repo)
        self.exercise = exercise()
        self.data = ExerciseCreate.model_validate(self.exercise.model_dump())
        self.repo.name_exists_visible.return_value = False
        self.repo.create.return_value = self.exercise
        self.repo.get_visible_by_id.return_value = self.exercise
        self.repo.update_owned.return_value = self.exercise
        self.repo.delete_owned.return_value = True

    def test_create_checks_visible_names_and_attributes_exercise_to_user(self) -> None:
        self.assertIs(self.service.create_exercise(self.data, USER_ID), self.exercise)
        self.repo.name_exists_visible.assert_called_once_with(self.data.name, USER_ID)
        self.repo.create.assert_called_once_with(self.data, USER_ID)

    def test_duplicate_visible_name_prevents_creation(self) -> None:
        self.repo.name_exists_visible.return_value = True
        with self.assertRaises(ExerciseNameAlreadyExistsError):
            self.service.create_exercise(self.data, USER_ID)
        self.repo.create.assert_not_called()

    def test_get_visible_exercise(self) -> None:
        self.assertIs(self.service.get_visible_by_user(EXERCISE_ID, USER_ID), self.exercise)
        self.repo.get_visible_by_id.assert_called_once_with(EXERCISE_ID, USER_ID)

    def test_invisible_exercise_is_not_found(self) -> None:
        self.repo.get_visible_by_id.return_value = None
        with self.assertRaises(ExerciseNotFoundError):
            self.service.get_visible_by_user(EXERCISE_ID, USER_ID)

    def test_list_preserves_pagination_and_false_filters(self) -> None:
        for results in ([self.exercise], []):
            with self.subTest(results=results):
                self.repo.list_visible.reset_mock()
                self.repo.list_visible.return_value = results
                self.assertEqual(
                    self.service.list_visible_by_user(
                        USER_ID,
                        limit=2,
                        offset=3,
                        search="squat",
                        muscle_group="Legs",
                        equipment="Barbell",
                        is_compound=False,
                        is_custom=False,
                    ),
                    results,
                )
                self.repo.list_visible.assert_called_once_with(
                    USER_ID,
                    2,
                    3,
                    "squat",
                    "Legs",
                    "Barbell",
                    False,
                    False,
                )

    def test_list_defaults_leave_filters_unset(self) -> None:
        self.repo.list_visible.return_value = []
        self.assertEqual(self.service.list_visible_by_user(USER_ID), [])
        self.repo.list_visible.assert_called_once_with(USER_ID, 100, 0, None, None, None, None, None)

    def test_rename_excludes_current_exercise_from_duplicate_check(self) -> None:
        updates = ExerciseUpdate(name="Front squat")
        self.assertIs(self.service.update_exercise(USER_ID, EXERCISE_ID, updates), self.exercise)
        self.repo.name_exists_visible.assert_called_once_with(
            "Front squat",
            USER_ID,
            exclude_exercise_id=EXERCISE_ID,
        )
        self.repo.update_owned.assert_called_once_with(USER_ID, EXERCISE_ID, updates)

    def test_duplicate_rename_prevents_update(self) -> None:
        self.repo.name_exists_visible.return_value = True
        with self.assertRaises(ExerciseUpdateError):
            self.service.update_exercise(USER_ID, EXERCISE_ID, ExerciseUpdate(name="Taken name"))
        self.repo.update_owned.assert_not_called()

    def test_non_name_and_empty_updates_skip_uniqueness_check(self) -> None:
        for updates in (ExerciseUpdate(is_compound=False), ExerciseUpdate()):
            with self.subTest(updates=updates):
                self.repo.update_owned.reset_mock()
                self.service.update_exercise(USER_ID, EXERCISE_ID, updates)
                self.repo.name_exists_visible.assert_not_called()
                self.repo.update_owned.assert_called_once_with(USER_ID, EXERCISE_ID, updates)

    def test_missing_or_foreign_exercise_cannot_be_updated(self) -> None:
        self.repo.update_owned.return_value = None
        with self.assertRaises(ExerciseNotFoundError):
            self.service.update_exercise(USER_ID, EXERCISE_ID, ExerciseUpdate(description="Changed"))

    def test_delete_custom_owned_exercise(self) -> None:
        self.service.delete_exercise(USER_ID, EXERCISE_ID)
        self.repo.get_visible_by_id.assert_called_once_with(EXERCISE_ID, USER_ID)
        self.repo.delete_owned.assert_called_once_with(USER_ID, EXERCISE_ID)

    def test_missing_exercise_cannot_be_deleted(self) -> None:
        self.repo.get_visible_by_id.return_value = None
        with self.assertRaises(ExerciseNotFoundError):
            self.service.delete_exercise(USER_ID, EXERCISE_ID)
        self.repo.delete_owned.assert_not_called()

    def test_predefined_exercise_cannot_be_deleted(self) -> None:
        self.repo.get_visible_by_id.return_value = self.exercise.model_copy(
            update={"is_custom": False, "created_by": None},
        )
        with self.assertRaises(ExerciseDeleteError):
            self.service.delete_exercise(USER_ID, EXERCISE_ID)
        self.repo.delete_owned.assert_not_called()

    def test_unsuccessful_owned_delete_is_reported(self) -> None:
        self.repo.delete_owned.return_value = False
        with self.assertRaises(ExerciseDeleteError):
            self.service.delete_exercise(USER_ID, EXERCISE_ID)

    def test_creation_and_update_wrap_repository_errors(self) -> None:
        failure = ExerciseRepositoryError("database unavailable")
        self.repo.create.side_effect = failure
        self.repo.update_owned.side_effect = failure
        with self.assertRaises(ExerciseCreationError) as creation:
            self.service.create_exercise(self.data, USER_ID)
        with self.assertRaises(ExerciseUpdateError) as update:
            self.service.update_exercise(USER_ID, EXERCISE_ID, ExerciseUpdate(is_compound=False))
        self.assertIs(creation.exception.__cause__, failure)
        self.assertIs(update.exception.__cause__, failure)
