"""Meal CRUD success, ownership guards, and failed writes."""

import unittest
from unittest.mock import create_autospec

from core.errors.meal import MealCreationError, MealDeleteError, MealNotFoundError, MealUpdateError
from core.errors.repository import MealRepositoryError
from ports.repositories.meal_repository import MealRepositoryPort
from schemas.meal_schema import MealCreate, MealUpdate
from services.meal_service import MealService
from tests.fixtures import MEAL_ID, TODAY, USER_ID, meal


class MealServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = create_autospec(MealRepositoryPort, instance=True, spec_set=True)
        self.service = MealService(self.repo)
        self.record = meal()
        self.data = MealCreate.model_validate(self.record.model_dump())
        self.updates = MealUpdate(name="Changed")
        self.repo.create.return_value = self.record
        self.repo.get_by_user_and_id.return_value = self.record
        self.repo.update_owned.return_value = self.record
        self.repo.delete_owned.return_value = True

    def test_create_attributes_record_to_authenticated_user(self) -> None:
        self.assertIs(self.service.create_meal(USER_ID, self.data), self.record)
        self.repo.create.assert_called_once_with(USER_ID, self.data)

    def test_get_visible_record(self) -> None:
        self.assertIs(self.service.get_visible_by_user(MEAL_ID, USER_ID), self.record)
        self.repo.get_by_user_and_id.assert_called_once_with(USER_ID, MEAL_ID)

    def test_missing_or_inaccessible_record_is_not_found(self) -> None:
        self.repo.get_by_user_and_id.return_value = None
        with self.assertRaises(MealNotFoundError):
            self.service.get_visible_by_user(MEAL_ID, USER_ID)

    def test_list_preserves_user_filters_and_pagination_including_empty_results(self) -> None:
        for results in ([self.record], []):
            with self.subTest(results=results):
                self.repo.list_by_user.return_value = results
                actual = self.service.list_visible_by_user(
                    USER_ID,
                    limit=2,
                    offset=3,
                    date_from=TODAY,
                    date_to=TODAY,
                    meal_type="breakfast",
                )
                self.assertEqual(actual, results)
                self.repo.list_by_user.assert_called_with(
                    user_id=USER_ID,
                    limit=2,
                    offset=3,
                    date_from=TODAY,
                    date_to=TODAY,
                    meal_type="breakfast",
                )

    def test_update_owned_record(self) -> None:
        self.repo.update_owned.return_value = self.record.model_copy(update={"name": "Changed"})
        result = self.service.update_meal(MEAL_ID, USER_ID, self.updates)
        self.assertEqual(result.name, "Changed")
        self.repo.get_by_user_and_id.assert_called_once_with(USER_ID, MEAL_ID)
        self.repo.update_owned.assert_called_once_with(USER_ID, MEAL_ID, self.updates)

    def test_empty_update_is_forwarded_without_inventing_values(self) -> None:
        updates = MealUpdate()
        self.assertIs(self.service.update_meal(MEAL_ID, USER_ID, updates), self.record)
        self.repo.update_owned.assert_called_once_with(USER_ID, MEAL_ID, updates)
        self.assertEqual(updates.model_dump(exclude_none=True), {})

    def test_missing_or_foreign_record_cannot_be_updated(self) -> None:
        self.repo.get_by_user_and_id.return_value = None
        with self.assertRaises(MealNotFoundError):
            self.service.update_meal(MEAL_ID, USER_ID, self.updates)
        self.repo.update_owned.assert_not_called()

    def test_record_disappearing_during_update_raises_not_found(self) -> None:
        self.repo.update_owned.return_value = None
        with self.assertRaises(MealNotFoundError):
            self.service.update_meal(MEAL_ID, USER_ID, self.updates)

    def test_delete_owned_record(self) -> None:
        self.service.delete_meal(MEAL_ID, USER_ID)
        self.repo.get_by_user_and_id.assert_called_once_with(USER_ID, MEAL_ID)
        self.repo.delete_owned.assert_called_once_with(USER_ID, MEAL_ID)

    def test_missing_or_foreign_record_cannot_be_deleted(self) -> None:
        self.repo.get_by_user_and_id.return_value = None
        with self.assertRaises(MealNotFoundError):
            self.service.delete_meal(MEAL_ID, USER_ID)
        self.repo.delete_owned.assert_not_called()

    def test_record_disappearing_during_delete_raises_not_found(self) -> None:
        self.repo.delete_owned.return_value = False
        with self.assertRaises(MealNotFoundError):
            self.service.delete_meal(MEAL_ID, USER_ID)

    def test_write_failures_raise_domain_errors_with_original_cause(self) -> None:
        failure = MealRepositoryError("database unavailable")
        self.repo.create.side_effect = failure
        self.repo.update_owned.side_effect = failure
        self.repo.delete_owned.side_effect = failure
        cases = (
            (MealCreationError, lambda: self.service.create_meal(USER_ID, self.data)),
            (MealUpdateError, lambda: self.service.update_meal(MEAL_ID, USER_ID, self.updates)),
            (MealDeleteError, lambda: self.service.delete_meal(MEAL_ID, USER_ID)),
        )
        for error, operation in cases:
            with (
                self.subTest(error=error.__name__),
                self.assertLogs("services.meal_service", level="ERROR"),
                self.assertRaises(error) as raised,
            ):
                operation()
            self.assertIs(raised.exception.__cause__, failure)
