"""Workout CRUD success, ownership guards, and failed writes."""

import unittest
from unittest.mock import create_autospec

from core.errors.repository import WorkoutRepositoryError
from core.errors.workout import (
    WorkoutCreationError,
    WorkoutDeleteError,
    WorkoutNotFoundError,
    WorkoutUpdateError,
)
from ports.repositories.workout_repository import WorkoutRepositoryPort
from schemas.workout_schema import WorkoutCreate, WorkoutUpdate
from services.workout_service import WorkoutService
from tests.fixtures import TODAY, USER_ID, WORKOUT_ID, workout


class WorkoutServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = create_autospec(WorkoutRepositoryPort, instance=True, spec_set=True)
        self.service = WorkoutService(self.repo)
        self.record = workout()
        self.data = WorkoutCreate.model_validate(self.record.model_dump())
        self.updates = WorkoutUpdate(name="Changed")
        self.repo.create.return_value = self.record
        self.repo.get_by_user_and_id.return_value = self.record
        self.repo.get_visible_by_id.return_value = self.record
        self.repo.update_owned.return_value = self.record
        self.repo.delete_owned.return_value = True

    def test_create_attributes_record_to_authenticated_user(self) -> None:
        self.assertIs(self.service.create_workout(USER_ID, self.data), self.record)
        self.repo.create.assert_called_once_with(USER_ID, self.data)

    def test_get_visible_record(self) -> None:
        self.assertIs(self.service.get_visible_by_user(WORKOUT_ID, USER_ID), self.record)
        self.repo.get_visible_by_id.assert_called_once_with(WORKOUT_ID, USER_ID)

    def test_missing_or_inaccessible_record_is_not_found(self) -> None:
        self.repo.get_visible_by_id.return_value = None
        with self.assertRaises(WorkoutNotFoundError):
            self.service.get_visible_by_user(WORKOUT_ID, USER_ID)

    def test_list_preserves_user_filters_and_pagination_including_empty_results(self) -> None:
        for results in ([self.record], []):
            with self.subTest(results=results):
                self.repo.get_all_visible_for_user.return_value = results
                actual = self.service.list_visible_by_user(
                    USER_ID,
                    search="Strength",
                    limit=2,
                    offset=3,
                    date_from=TODAY,
                    date_to=TODAY,
                )
                self.assertEqual(actual, results)
                self.repo.get_all_visible_for_user.assert_called_with(USER_ID, "Strength", 2, 3, TODAY, TODAY)

    def test_update_owned_record(self) -> None:
        self.repo.update_owned.return_value = self.record.model_copy(update={"name": "Changed"})
        result = self.service.update_workout(WORKOUT_ID, USER_ID, self.updates)
        self.assertEqual(result.name, "Changed")
        self.repo.get_by_user_and_id.assert_called_once_with(USER_ID, WORKOUT_ID)
        self.repo.update_owned.assert_called_once_with(USER_ID, WORKOUT_ID, self.updates)

    def test_empty_update_is_forwarded_without_inventing_values(self) -> None:
        updates = WorkoutUpdate()
        self.assertIs(self.service.update_workout(WORKOUT_ID, USER_ID, updates), self.record)
        self.repo.update_owned.assert_called_once_with(USER_ID, WORKOUT_ID, updates)
        self.assertEqual(updates.model_dump(exclude_none=True), {})

    def test_missing_or_foreign_record_cannot_be_updated(self) -> None:
        self.repo.get_by_user_and_id.return_value = None
        with self.assertRaises(WorkoutNotFoundError):
            self.service.update_workout(WORKOUT_ID, USER_ID, self.updates)
        self.repo.update_owned.assert_not_called()

    def test_record_disappearing_during_update_raises_not_found(self) -> None:
        self.repo.update_owned.return_value = None
        with self.assertRaises(WorkoutNotFoundError):
            self.service.update_workout(WORKOUT_ID, USER_ID, self.updates)

    def test_delete_owned_record(self) -> None:
        self.service.delete_workout(WORKOUT_ID, USER_ID)
        self.repo.get_by_user_and_id.assert_called_once_with(USER_ID, WORKOUT_ID)
        self.repo.delete_owned.assert_called_once_with(USER_ID, WORKOUT_ID)

    def test_missing_or_foreign_record_cannot_be_deleted(self) -> None:
        self.repo.get_by_user_and_id.return_value = None
        with self.assertRaises(WorkoutNotFoundError):
            self.service.delete_workout(WORKOUT_ID, USER_ID)
        self.repo.delete_owned.assert_not_called()

    def test_record_disappearing_during_delete_raises_not_found(self) -> None:
        self.repo.delete_owned.return_value = False
        with self.assertRaises(WorkoutNotFoundError):
            self.service.delete_workout(WORKOUT_ID, USER_ID)

    def test_write_failures_raise_domain_errors_with_original_cause(self) -> None:
        failure = WorkoutRepositoryError("database unavailable")
        self.repo.create.side_effect = failure
        self.repo.update_owned.side_effect = failure
        self.repo.delete_owned.side_effect = failure
        cases = (
            (WorkoutCreationError, lambda: self.service.create_workout(USER_ID, self.data)),
            (WorkoutUpdateError, lambda: self.service.update_workout(WORKOUT_ID, USER_ID, self.updates)),
            (WorkoutDeleteError, lambda: self.service.delete_workout(WORKOUT_ID, USER_ID)),
        )
        for error, operation in cases:
            with (
                self.subTest(error=error.__name__),
                self.assertLogs("services.workout_service", level="ERROR"),
                self.assertRaises(error) as raised,
            ):
                operation()
            self.assertIs(raised.exception.__cause__, failure)
