"""Owned body weight CRUD, duplicate-date checks, races, and persistence failures."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest import TestCase
from unittest.mock import create_autospec, patch

from core.errors.body_weight_entry import (
    BodyWeightEntryCreationError,
    BodyWeightEntryDateConflictError,
    BodyWeightEntryNotFoundError,
    BodyWeightEntryUpdateError,
)
from core.errors.database import DatabaseError
from core.errors.repository import (
    BodyWeightEntryDateConflictRepositoryError,
    BodyWeightEntryRepositoryError,
    BodyWeightEntryRowError,
)
from ports.repositories.body_weight_entry_repository import BodyWeightEntryRepositoryPort
from schemas.body_weight_entry_schema import BodyWeightEntryCreate, BodyWeightEntryUpdate
from services.body_weight_entry_service import BodyWeightEntryService
from tests.fixtures import TODAY, USER_ID, WEIGHT_ENTRY_ID, weight_entry
from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET

if TYPE_CHECKING:
    from collections.abc import Callable


class BodyWeightEntryServiceTests(TestCase):
    def setUp(self) -> None:
        self.repo = create_autospec(BodyWeightEntryRepositoryPort, instance=True, spec_set=True)
        self.service = BodyWeightEntryService(self.repo)
        self.logger = self.enterContext(patch.object(self.service, "logger"))
        self.entry = weight_entry()
        self.data = BodyWeightEntryCreate.model_validate(self.entry.model_dump())
        self.repo.create.return_value = self.entry
        self.repo.get_by_user_and_id.return_value = self.entry
        self.repo.get_by_user_and_date.return_value = None
        self.repo.get_latest_for_user.return_value = self.entry
        self.repo.list_by_user.return_value = [self.entry]
        self.repo.update_owned.return_value = self.entry
        self.repo.delete_owned.return_value = True

    def test_create_checks_own_date_and_returns_persisted_entry(self) -> None:
        self.assertIs(self.service.create(USER_ID, self.data), self.entry)
        self.assertEqual([event[0] for event in self.repo.mock_calls], ["get_by_user_and_date", "create"])
        self.repo.get_by_user_and_date.assert_called_once_with(USER_ID, TODAY)
        self.repo.create.assert_called_once_with(USER_ID, self.data)
        self.logger.info.assert_called_once()

    def test_create_rejects_existing_date_before_writing(self) -> None:
        self.repo.get_by_user_and_date.return_value = self.entry
        with self.assertRaises(BodyWeightEntryDateConflictError) as raised:
            self.service.create(USER_ID, self.data)
        self.assertIn(TODAY.isoformat(), str(raised.exception))
        self.repo.create.assert_not_called()
        self.logger.info.assert_not_called()

    def test_create_preserves_decimal_boundary_weights_without_conversion(self) -> None:
        for value in (Decimal("0.01"), Decimal("75.50"), Decimal("999.99")):
            with self.subTest(weight=value):
                self.repo.reset_mock()
                data = BodyWeightEntryCreate(weight=value, entry_date=TODAY)
                expected = self.entry.model_copy(update={"weight": value})
                self.repo.create.return_value = expected
                self.assertIs(self.service.create(USER_ID, data), expected)
                self.repo.create.assert_called_once_with(USER_ID, data)
                self.assertEqual(data.weight, value)

    def test_create_translates_concurrent_date_conflict_and_preserves_cause(self) -> None:
        failure = BodyWeightEntryDateConflictRepositoryError(TODAY)
        self.repo.create.side_effect = failure
        with self.assertRaises(BodyWeightEntryDateConflictError) as raised:
            self.service.create(USER_ID, self.data)
        self.assertIs(raised.exception.__cause__, failure)
        self.assertIn(TODAY.isoformat(), str(raised.exception))
        self.logger.info.assert_not_called()

    def test_repository_creation_failure_is_wrapped_without_private_details(self) -> None:
        failure = BodyWeightEntryRepositoryError("private SQL values")
        self.repo.create.side_effect = failure
        with self.assertRaises(BodyWeightEntryCreationError) as raised:
            self.service.create(USER_ID, self.data)
        self.assertIs(raised.exception.__cause__, failure)
        self.assertNotIn("private", str(raised.exception))
        self.logger.info.assert_not_called()

    def test_get_by_id_uses_owned_lookup_only(self) -> None:
        self.assertIs(self.service.get_by_id(USER_ID, WEIGHT_ENTRY_ID), self.entry)
        self.repo.get_by_user_and_id.assert_called_once_with(USER_ID, WEIGHT_ENTRY_ID)
        self.repo.get_by_id.assert_not_called()

    def test_get_by_date_passes_exact_date_and_user(self) -> None:
        self.repo.get_by_user_and_date.return_value = self.entry
        self.assertIs(self.service.get_by_date(USER_ID, TODAY), self.entry)
        self.repo.get_by_user_and_date.assert_called_once_with(USER_ID, TODAY)

    def test_latest_returns_entry_or_reports_empty_history(self) -> None:
        self.assertIs(self.service.get_latest(USER_ID), self.entry)
        self.repo.get_latest_for_user.assert_called_once_with(USER_ID)
        self.repo.get_latest_for_user.return_value = None
        with self.assertRaises(BodyWeightEntryNotFoundError) as raised:
            self.service.get_latest(USER_ID)
        self.assertEqual(str(raised.exception), f"User with ID {USER_ID} has no body weight entries.")

    def test_missing_id_and_date_use_lookup_specific_errors(self) -> None:
        self.repo.get_by_user_and_id.return_value = None
        with self.assertRaises(BodyWeightEntryNotFoundError) as by_id:
            self.service.get_by_id(USER_ID, WEIGHT_ENTRY_ID)
        with self.assertRaises(BodyWeightEntryNotFoundError) as by_date:
            self.service.get_by_date(USER_ID, TODAY)
        self.assertEqual(str(by_id.exception), f"Body weight entry with ID {WEIGHT_ENTRY_ID} not found.")
        self.assertEqual(str(by_date.exception), f"Body weight entry for {TODAY.isoformat()} not found.")

    def test_list_forwards_shared_defaults_and_returns_empty_or_nonempty_results(self) -> None:
        for entries in ([self.entry], []):
            with self.subTest(size=len(entries)):
                self.repo.list_by_user.reset_mock()
                self.repo.list_by_user.return_value = entries
                self.assertEqual(self.service.list_by_user(USER_ID), entries)
                self.repo.list_by_user.assert_called_once_with(
                    USER_ID, DEFAULT_LIMIT, DEFAULT_OFFSET, None, None
                )
        self.repo.get_by_id.assert_not_called()

    def test_list_preserves_pagination_and_inclusive_optional_date_filters(self) -> None:
        for lower, upper in ((None, TODAY), (TODAY, None), (TODAY, TODAY), (TODAY, TODAY - timedelta(days=1))):
            for limit, offset in ((1, 0), (1000, 1000), (0, -1)):
                with self.subTest(lower=lower, upper=upper, limit=limit, offset=offset):
                    self.repo.list_by_user.reset_mock()
                    self.service.list_by_user(USER_ID, limit, offset, lower, upper)
                    self.repo.list_by_user.assert_called_once_with(USER_ID, limit, offset, lower, upper)

    def test_missing_or_foreign_entries_block_mutations_before_date_checks(self) -> None:
        self.repo.get_by_user_and_id.return_value = None
        for operation in (
            lambda: self.service.update(
                USER_ID, WEIGHT_ENTRY_ID, BodyWeightEntryUpdate(entry_date=TODAY + timedelta(days=1))
            ),
            lambda: self.service.delete(USER_ID, WEIGHT_ENTRY_ID),
        ):
            with self.subTest(operation=operation), self.assertRaises(BodyWeightEntryNotFoundError):
                operation()
        self.repo.get_by_user_and_date.assert_not_called()
        self.repo.update_owned.assert_not_called()
        self.repo.delete_owned.assert_not_called()
        self.repo.get_by_id.assert_not_called()

    def test_update_accepts_empty_null_same_date_and_weight_changes(self) -> None:
        payloads = (
            BodyWeightEntryUpdate(),
            BodyWeightEntryUpdate(entry_date=None, weight=None),
            BodyWeightEntryUpdate(entry_date=TODAY),
            BodyWeightEntryUpdate(weight=Decimal("0.01")),
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                self.repo.reset_mock()
                self.assertIs(self.service.update(USER_ID, WEIGHT_ENTRY_ID, payload), self.entry)
                self.repo.update_owned.assert_called_once_with(USER_ID, WEIGHT_ENTRY_ID, payload)
                self.repo.get_by_user_and_id.assert_called_once_with(USER_ID, WEIGHT_ENTRY_ID)
                self.repo.get_by_user_and_date.assert_not_called()

    def test_update_accepts_free_date_and_a_reread_of_the_same_entry(self) -> None:
        new_date = TODAY + timedelta(days=1)
        for conflict in (None, self.entry.model_copy(update={"entry_date": new_date})):
            with self.subTest(same_entry=conflict is not None):
                self.repo.reset_mock()
                self.repo.get_by_user_and_date.return_value = conflict
                data = BodyWeightEntryUpdate(entry_date=new_date)
                self.assertIs(self.service.update(USER_ID, WEIGHT_ENTRY_ID, data), self.entry)
                self.repo.get_by_user_and_date.assert_called_once_with(USER_ID, new_date)
                self.repo.update_owned.assert_called_once_with(USER_ID, WEIGHT_ENTRY_ID, data)

    def test_update_rejects_date_occupied_by_another_owned_entry(self) -> None:
        new_date = TODAY + timedelta(days=1)
        self.repo.get_by_user_and_date.return_value = self.entry.model_copy(
            update={"id": 99, "entry_date": new_date}
        )
        with self.assertRaises(BodyWeightEntryDateConflictError) as raised:
            self.service.update(USER_ID, WEIGHT_ENTRY_ID, BodyWeightEntryUpdate(entry_date=new_date))
        self.assertIn(new_date.isoformat(), str(raised.exception))
        self.assertNotIn("99", str(raised.exception))
        self.repo.update_owned.assert_not_called()
        self.logger.info.assert_not_called()

    def test_update_translates_concurrent_date_conflict_with_original_cause(self) -> None:
        new_date = TODAY + timedelta(days=1)
        failure = BodyWeightEntryDateConflictRepositoryError(new_date)
        self.repo.update_owned.side_effect = failure
        with self.assertRaises(BodyWeightEntryDateConflictError) as raised:
            self.service.update(USER_ID, WEIGHT_ENTRY_ID, BodyWeightEntryUpdate(entry_date=new_date))
        self.assertIs(raised.exception.__cause__, failure)
        self.assertIn(new_date.isoformat(), str(raised.exception))
        self.logger.info.assert_not_called()

    def test_update_wraps_repository_errors_without_private_details(self) -> None:
        failure = BodyWeightEntryRepositoryError("private update SQL")
        self.repo.update_owned.side_effect = failure
        with self.assertRaises(BodyWeightEntryUpdateError) as raised:
            self.service.update(USER_ID, WEIGHT_ENTRY_ID, BodyWeightEntryUpdate(weight=Decimal("76.25")))
        self.assertIs(raised.exception.__cause__, failure)
        self.assertNotIn("private", str(raised.exception))
        self.logger.info.assert_not_called()

    def test_update_disappearing_after_ownership_check_raises_not_found(self) -> None:
        self.repo.update_owned.return_value = None
        with self.assertRaises(BodyWeightEntryNotFoundError) as raised:
            self.service.update(USER_ID, WEIGHT_ENTRY_ID, BodyWeightEntryUpdate())
        self.assertEqual(
            str(raised.exception), str(BodyWeightEntryNotFoundError.not_accessible(WEIGHT_ENTRY_ID))
        )
        self.logger.info.assert_not_called()

    def test_delete_checks_ownership_and_deletes_exact_entry(self) -> None:
        self.assertIsNone(self.service.delete(USER_ID, WEIGHT_ENTRY_ID))
        self.assertEqual([event[0] for event in self.repo.mock_calls], ["get_by_user_and_id", "delete_owned"])
        self.repo.delete_owned.assert_called_once_with(USER_ID, WEIGHT_ENTRY_ID)
        self.logger.info.assert_called_once()

    def test_delete_disappearing_after_ownership_check_is_not_found(self) -> None:
        self.repo.delete_owned.return_value = False
        with self.assertRaises(BodyWeightEntryNotFoundError) as raised:
            self.service.delete(USER_ID, WEIGHT_ENTRY_ID)
        self.assertEqual(
            str(raised.exception), str(BodyWeightEntryNotFoundError.not_accessible(WEIGHT_ENTRY_ID))
        )
        self.logger.info.assert_not_called()

    def test_lookup_and_write_failures_preserve_types_and_never_log_success(self) -> None:
        cases: tuple[tuple[str, Callable[[], object]], ...] = (
            ("get_by_user_and_date", lambda: self.service.create(USER_ID, self.data)),
            ("get_by_user_and_date", lambda: self.service.get_by_date(USER_ID, TODAY)),
            ("get_by_user_and_id", lambda: self.service.get_by_id(USER_ID, WEIGHT_ENTRY_ID)),
            ("get_latest_for_user", lambda: self.service.get_latest(USER_ID)),
            ("list_by_user", lambda: self.service.list_by_user(USER_ID)),
            (
                "get_by_user_and_id",
                lambda: self.service.update(USER_ID, WEIGHT_ENTRY_ID, BodyWeightEntryUpdate()),
            ),
            (
                "get_by_user_and_date",
                lambda: self.service.update(
                    USER_ID, WEIGHT_ENTRY_ID, BodyWeightEntryUpdate(entry_date=TODAY + timedelta(days=1))
                ),
            ),
            ("get_by_user_and_id", lambda: self.service.delete(USER_ID, WEIGHT_ENTRY_ID)),
            ("delete_owned", lambda: self.service.delete(USER_ID, WEIGHT_ENTRY_ID)),
        )
        for method, operation in cases:
            for error in (
                DatabaseError("failure"),
                BodyWeightEntryRowError("invalid row"),
                BodyWeightEntryRepositoryError("failure"),
            ):
                with (
                    self.subTest(method=method, error=type(error).__name__),
                    patch.object(self.repo, method, side_effect=error),
                    self.assertRaises(type(error)) as raised,
                ):
                    operation()
                self.assertIs(raised.exception, error)
        for method, operation in (
            ("create", lambda: self.service.create(USER_ID, self.data)),
            ("update_owned", lambda: self.service.update(USER_ID, WEIGHT_ENTRY_ID, BodyWeightEntryUpdate())),
        ):
            for error in (DatabaseError("failure"), BodyWeightEntryRowError("invalid row")):
                with (
                    self.subTest(method=method),
                    patch.object(self.repo, method, side_effect=error),
                    self.assertRaises(type(error)) as raised,
                ):
                    operation()
                self.assertIs(raised.exception, error)
        self.logger.info.assert_not_called()
