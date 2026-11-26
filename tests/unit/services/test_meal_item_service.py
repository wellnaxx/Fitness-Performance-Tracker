"""Meal-item CRUD, ownership-first access, partial updates, and failure boundaries."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from unittest import TestCase
from unittest.mock import Mock, call, create_autospec, patch

from core.errors.database import DatabaseError
from core.errors.meal import MealNotFoundError
from core.errors.meal_item import (
    MealItemCreationError,
    MealItemDeleteError,
    MealItemNotFoundError,
    MealItemUpdateError,
)
from core.errors.repository import MealItemRepositoryError, MealItemRowError, MealRepositoryError, MealRowError
from ports.repositories.meal_item_repository import MealItemRepositoryPort
from ports.repositories.meal_repository import MealRepositoryPort
from schemas.meal_item_schema import MealItemCreate, MealItemPublic, MealItemUpdate
from services.meal_item_service import MealItemService
from tests.fixtures import MEAL_ID, MEAL_ITEM_ID, USER_ID, meal, meal_item

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.errors.base import ServiceError


class MealItemServiceTests(TestCase):
    def setUp(self) -> None:
        self.meals = create_autospec(MealRepositoryPort, instance=True, spec_set=True)
        self.items = create_autospec(MealItemRepositoryPort, instance=True, spec_set=True)
        self.service = MealItemService(self.meals, self.items)
        self.logger = self.enterContext(patch.object(self.service, "logger"))
        self.events = Mock()
        self.events.attach_mock(self.meals, "meals")
        self.events.attach_mock(self.items, "items")
        self.item = meal_item()
        self.data = MealItemCreate.model_validate(self.item.model_dump())
        self.updates = MealItemUpdate(name="Updated oats")
        self.meals.get_by_user_and_id.return_value = meal()
        self.items.create.return_value = self.item
        self.items.get_by_meal_and_id.return_value = self.item
        self.items.list_by_meal.return_value = [self.item]
        self.items.update_in_meal.return_value = self.item
        self.items.delete_in_meal.return_value = True

    def _operations(self) -> tuple[tuple[str, Callable[[], object]], ...]:
        return (
            ("create", lambda: self.service.create(USER_ID, self.data)),
            ("get", lambda: self.service.get_by_id(USER_ID, MEAL_ID, MEAL_ITEM_ID)),
            ("list", lambda: self.service.list_by_meal(USER_ID, MEAL_ID)),
            ("update", lambda: self.service.update(USER_ID, MEAL_ID, MEAL_ITEM_ID, self.updates)),
            ("delete", lambda: self.service.delete(USER_ID, MEAL_ID, MEAL_ITEM_ID)),
        )

    def test_create_checks_payload_meal_ownership_before_inserting(self) -> None:
        self.assertIs(self.service.create(USER_ID, self.data), self.item)
        self.assertEqual(
            self.events.mock_calls,
            [call.meals.get_by_user_and_id(USER_ID, MEAL_ID), call.items.create(self.data)],
        )
        self.logger.info.assert_called_once()
        self.items.get_by_id.assert_not_called()

    def test_create_preserves_zero_decimals_optional_serving_size_and_name_boundaries(self) -> None:
        for name in ("A", "x" * 100, "Овес", "Oats'; DROP TABLE meals; --"):
            for serving_size in (None, Decimal("0"), Decimal("0.01"), Decimal("50.25")):
                with self.subTest(name=name, serving_size=serving_size):
                    self.events.reset_mock()
                    data = MealItemCreate(
                        meal_id=MEAL_ID,
                        name=name,
                        serving_size=serving_size,
                        calories=Decimal("0"),
                        protein=Decimal("0.01"),
                        carbs=Decimal("123.45"),
                        fats=Decimal("0"),
                    )
                    snapshot = data.model_dump()
                    expected = MealItemPublic.model_validate({**self.item.model_dump(), **snapshot})
                    self.items.create.return_value = expected
                    self.assertIs(self.service.create(USER_ID, data), expected)
                    self.items.create.assert_called_once_with(data)
                    self.assertEqual(data.model_dump(), snapshot)

    def test_all_operations_reject_missing_or_foreign_parents_before_accessing_items(self) -> None:
        self.meals.get_by_user_and_id.return_value = None
        for name, operation in self._operations():
            with self.subTest(operation=name):
                self.events.reset_mock()
                self.logger.reset_mock()
                with self.assertRaises(MealNotFoundError) as raised:
                    operation()
                self.assertEqual(str(raised.exception), str(MealNotFoundError.not_accessible(MEAL_ID)))
                self.assertEqual(self.events.mock_calls, [call.meals.get_by_user_and_id(USER_ID, MEAL_ID)])
                self.logger.info.assert_not_called()
                self.logger.debug.assert_not_called()

    def test_parent_lookup_failures_propagate_without_accessing_items(self) -> None:
        for name, operation in self._operations():
            for failure in (
                DatabaseError("private database error"),
                MealRepositoryError("private repository error"),
                MealRowError("invalid stored meal"),
                RuntimeError("unexpected error"),
            ):
                with self.subTest(operation=name, error=type(failure).__name__):
                    self.events.reset_mock()
                    self.logger.reset_mock()
                    with (
                        patch.object(self.meals, "get_by_user_and_id", side_effect=failure),
                        self.assertRaises(type(failure)) as raised,
                    ):
                        operation()
                    self.assertIs(raised.exception, failure)
                    self.assertEqual(self.items.mock_calls, [])
                    self.logger.info.assert_not_called()

    def test_get_returns_item_after_owned_parent_and_scoped_lookup(self) -> None:
        self.assertIs(self.service.get_by_id(USER_ID, MEAL_ID, MEAL_ITEM_ID), self.item)
        self.assertEqual(
            self.events.mock_calls,
            [
                call.meals.get_by_user_and_id(USER_ID, MEAL_ID),
                call.items.get_by_meal_and_id(MEAL_ID, MEAL_ITEM_ID),
            ],
        )
        self.items.get_by_id.assert_not_called()
        self.logger.debug.assert_called_once()
        self.logger.info.assert_not_called()

    def test_list_preserves_empty_single_and_multiple_results_without_pagination(self) -> None:
        another = self.item.model_copy(update={"id": MEAL_ITEM_ID + 1, "name": "Rice"})
        results: tuple[list[MealItemPublic], ...] = ([], [self.item], [self.item, another])
        for entries in results:
            with self.subTest(size=len(entries)):
                self.events.reset_mock()
                self.logger.reset_mock()
                self.items.list_by_meal.return_value = entries
                self.assertIs(self.service.list_by_meal(USER_ID, MEAL_ID), entries)
                self.assertEqual(
                    self.events.mock_calls,
                    [call.meals.get_by_user_and_id(USER_ID, MEAL_ID), call.items.list_by_meal(MEAL_ID)],
                )
                self.logger.debug.assert_called_once()
                self.logger.info.assert_not_called()

    def test_missing_or_wrong_parent_items_raise_item_errors_and_block_writes(self) -> None:
        self.items.get_by_meal_and_id.return_value = None
        for name, operation in self._operations():
            if name not in {"get", "update", "delete"}:
                continue
            with self.subTest(operation=name):
                self.events.reset_mock()
                self.logger.reset_mock()
                with self.assertRaises(MealItemNotFoundError) as raised:
                    operation()
                self.assertEqual(
                    str(raised.exception), str(MealItemNotFoundError.not_in_meal(MEAL_ITEM_ID, MEAL_ID))
                )
                self.assertEqual(
                    self.events.mock_calls,
                    [
                        call.meals.get_by_user_and_id(USER_ID, MEAL_ID),
                        call.items.get_by_meal_and_id(MEAL_ID, MEAL_ITEM_ID),
                    ],
                )
                self.items.get_by_id.assert_not_called()
                self.logger.warning.assert_called_once()
                self.logger.info.assert_not_called()

    def test_update_checks_parent_and_item_then_returns_persisted_values(self) -> None:
        expected = self.item.model_copy(update={"name": self.updates.name})
        self.items.update_in_meal.return_value = expected
        self.assertIs(self.service.update(USER_ID, MEAL_ID, MEAL_ITEM_ID, self.updates), expected)
        self.assertEqual(
            self.events.mock_calls,
            [
                call.meals.get_by_user_and_id(USER_ID, MEAL_ID),
                call.items.get_by_meal_and_id(MEAL_ID, MEAL_ITEM_ID),
                call.items.update_in_meal(MEAL_ID, MEAL_ITEM_ID, self.updates),
            ],
        )
        self.assertEqual(self.item.name, "Oats")
        self.logger.info.assert_called_once()

    def test_update_forwards_each_supported_field_and_all_fields_without_mutation(self) -> None:
        values: dict[str, object] = {
            "name": "Rice",
            "serving_size": Decimal("0"),
            "calories": Decimal("0"),
            "protein": Decimal("0.01"),
            "carbs": Decimal("125.25"),
            "fats": Decimal("0"),
        }
        payloads = [MealItemUpdate.model_validate({field: value}) for field, value in values.items()]
        payloads.append(MealItemUpdate.model_validate(values))
        for payload in payloads:
            with self.subTest(fields=payload.model_fields_set):
                self.items.reset_mock()
                snapshot = payload.model_dump()
                expected = MealItemPublic.model_validate(
                    {**self.item.model_dump(), **payload.model_dump(exclude_none=True)}
                )
                self.items.update_in_meal.return_value = expected
                self.assertIs(self.service.update(USER_ID, MEAL_ID, MEAL_ITEM_ID, payload), expected)
                self.items.update_in_meal.assert_called_once_with(MEAL_ID, MEAL_ITEM_ID, payload)
                self.assertEqual(payload.model_dump(), snapshot)

    def test_empty_all_null_and_mixed_updates_are_delegated_after_access_checks(self) -> None:
        payloads = (
            MealItemUpdate(),
            MealItemUpdate(name=None, serving_size=None, calories=None, protein=None, carbs=None, fats=None),
            MealItemUpdate(name="Rice", serving_size=None, calories=Decimal("0")),
        )
        for payload in payloads:
            with self.subTest(fields=payload.model_fields_set):
                self.events.reset_mock()
                self.assertIs(self.service.update(USER_ID, MEAL_ID, MEAL_ITEM_ID, payload), self.item)
                self.meals.get_by_user_and_id.assert_called_once_with(USER_ID, MEAL_ID)
                self.items.get_by_meal_and_id.assert_called_once_with(MEAL_ID, MEAL_ITEM_ID)
                self.items.update_in_meal.assert_called_once_with(MEAL_ID, MEAL_ITEM_ID, payload)

    def test_update_disappearing_item_is_not_found_without_success_logging(self) -> None:
        self.items.update_in_meal.return_value = None
        with self.assertRaises(MealItemNotFoundError) as raised:
            self.service.update(USER_ID, MEAL_ID, MEAL_ITEM_ID, self.updates)
        self.assertEqual(str(raised.exception), str(MealItemNotFoundError.not_accessible(MEAL_ITEM_ID)))
        self.items.update_in_meal.assert_called_once_with(MEAL_ID, MEAL_ITEM_ID, self.updates)
        self.logger.warning.assert_called_once()
        self.logger.info.assert_not_called()

    def test_delete_checks_parent_and_item_then_deletes_exact_item(self) -> None:
        self.assertIsNone(self.service.delete(USER_ID, MEAL_ID, MEAL_ITEM_ID))
        self.assertEqual(
            self.events.mock_calls,
            [
                call.meals.get_by_user_and_id(USER_ID, MEAL_ID),
                call.items.get_by_meal_and_id(MEAL_ID, MEAL_ITEM_ID),
                call.items.delete_in_meal(MEAL_ID, MEAL_ITEM_ID),
            ],
        )
        self.logger.info.assert_called_once()

    def test_delete_disappearing_item_is_not_found_without_success_logging(self) -> None:
        self.items.delete_in_meal.return_value = False
        with self.assertRaises(MealItemNotFoundError) as raised:
            self.service.delete(USER_ID, MEAL_ID, MEAL_ITEM_ID)
        self.assertEqual(str(raised.exception), str(MealItemNotFoundError.not_accessible(MEAL_ITEM_ID)))
        self.logger.warning.assert_called_once()
        self.logger.info.assert_not_called()

    def test_item_write_repository_failures_are_translated_with_safe_messages_and_causes(self) -> None:
        cases: tuple[tuple[str, Callable[[], object], type[ServiceError]], ...] = (
            ("create", lambda: self.service.create(USER_ID, self.data), MealItemCreationError),
            (
                "update_in_meal",
                lambda: self.service.update(USER_ID, MEAL_ID, MEAL_ITEM_ID, self.updates),
                MealItemUpdateError,
            ),
            (
                "delete_in_meal",
                lambda: self.service.delete(USER_ID, MEAL_ID, MEAL_ITEM_ID),
                MealItemDeleteError,
            ),
        )
        for method, operation, expected_error in cases:
            failure = MealItemRepositoryError("private SQL credentials and item values")
            with self.subTest(method=method):
                self.logger.reset_mock()
                with (
                    patch.object(self.items, method, side_effect=failure),
                    self.assertRaises(expected_error) as raised,
                ):
                    operation()
                self.assertIs(raised.exception.__cause__, failure)
                self.assertNotIn("private", str(raised.exception))
                self.logger.exception.assert_called_once()
                self.logger.info.assert_not_called()

    def test_item_read_failures_propagate_and_never_reach_mutations(self) -> None:
        cases: tuple[tuple[str, Callable[[], object]], ...] = (
            ("get_by_meal_and_id", lambda: self.service.get_by_id(USER_ID, MEAL_ID, MEAL_ITEM_ID)),
            ("list_by_meal", lambda: self.service.list_by_meal(USER_ID, MEAL_ID)),
            ("get_by_meal_and_id", lambda: self.service.update(USER_ID, MEAL_ID, MEAL_ITEM_ID, self.updates)),
            ("get_by_meal_and_id", lambda: self.service.delete(USER_ID, MEAL_ID, MEAL_ITEM_ID)),
        )
        for method, operation in cases:
            for failure in (
                DatabaseError("database error"),
                MealItemRowError("invalid row"),
                MealItemRepositoryError("repository error"),
            ):
                with self.subTest(method=method, error=type(failure).__name__):
                    self.events.reset_mock()
                    self.logger.reset_mock()
                    with (
                        patch.object(self.items, method, side_effect=failure),
                        self.assertRaises(type(failure)) as raised,
                    ):
                        operation()
                    self.assertIs(raised.exception, failure)
                    self.items.create.assert_not_called()
                    self.items.update_in_meal.assert_not_called()
                    self.items.delete_in_meal.assert_not_called()
                    self.logger.info.assert_not_called()

    def test_write_database_row_and_unexpected_errors_keep_original_types(self) -> None:
        cases: tuple[tuple[str, Callable[[], object]], ...] = (
            ("create", lambda: self.service.create(USER_ID, self.data)),
            ("update_in_meal", lambda: self.service.update(USER_ID, MEAL_ID, MEAL_ITEM_ID, self.updates)),
            ("delete_in_meal", lambda: self.service.delete(USER_ID, MEAL_ID, MEAL_ITEM_ID)),
        )
        for method, operation in cases:
            for failure in (
                DatabaseError("database error"),
                MealItemRowError("invalid row"),
                RuntimeError("unexpected error"),
            ):
                with self.subTest(method=method, error=type(failure).__name__):
                    self.logger.reset_mock()
                    with (
                        patch.object(self.items, method, side_effect=failure),
                        self.assertRaises(type(failure)) as raised,
                    ):
                        operation()
                    self.assertIs(raised.exception, failure)
                    self.logger.info.assert_not_called()
