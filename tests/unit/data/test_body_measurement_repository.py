"""Measurement SQL binding, partial changes, and precise PostgreSQL conflict translation."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from psycopg.errors import CheckViolation, UniqueViolation
from psycopg.pq import DiagnosticField

from core.errors.database import DatabaseError
from core.errors.repository import (
    BodyMeasurementDateConflictRepositoryError,
    BodyMeasurementRepositoryError,
    BodyMeasurementRowError,
)
from data import executor
from data.queries import QUERIES
from repositories.body_measurement_repository import BodyMeasurementRepository
from schemas.body_measurement_schema import BodyMeasurementCreate, BodyMeasurementUpdate
from tests.fixtures import MEASUREMENT_ID, TODAY, USER_ID, measurement

if TYPE_CHECKING:
    from collections.abc import Callable


DATE_CONSTRAINT = "body_measurements_user_id_entry_date_key"


def unique_violation(constraint: str | None = DATE_CONSTRAINT) -> UniqueViolation:
    """Build a real psycopg exception with server-style constraint diagnostics."""
    info: dict[int, bytes | None] = {
        DiagnosticField.CONSTRAINT_NAME: constraint.encode() if constraint else None
    }
    return UniqueViolation("private database details", info=info)


def database_failure(cause: Exception | None) -> DatabaseError:
    """Reproduce the shared executor's explicit driver-error cause chain."""
    error = DatabaseError("private database details")
    error.__cause__ = cause
    return error


class BodyMeasurementRepositoryTests(TestCase):
    def setUp(self) -> None:
        self.repo = BodyMeasurementRepository()
        self.entry = measurement()
        self.row = self.entry.model_dump()
        self.data = BodyMeasurementCreate.model_validate(self.row)
        self.fetch_one = self.enterContext(
            patch("repositories.body_measurement_repository.fetch_one", return_value=self.row)
        )
        self.fetch_all = self.enterContext(
            patch("repositories.body_measurement_repository.fetch_all", return_value=[self.row])
        )
        self.insert = self.enterContext(
            patch("repositories.body_measurement_repository.execute_insert", return_value=MEASUREMENT_ID)
        )
        self.write = self.enterContext(
            patch("repositories.body_measurement_repository.execute_write", return_value=1)
        )
        self.enterContext(patch("repositories.body_measurement_repository.logger"))

    def test_create_binds_all_values_and_reads_back_assigned_id(self) -> None:
        self.assertEqual(self.repo.create(USER_ID, self.data), self.entry)
        sql, params = self.insert.call_args.args
        self.assertEqual(sql, QUERIES.body_measurements.create)
        self.assertEqual(params, (USER_ID, *self.data.model_dump().values()))
        self.assertEqual(sql.count("%s"), len(params))
        self.fetch_one.assert_called_once_with(QUERIES.body_measurements.get_by_id, (MEASUREMENT_ID,))

    def test_create_missing_readback_raises_repository_error(self) -> None:
        self.fetch_one.return_value = None
        with self.assertRaises(BodyMeasurementRepositoryError):
            self.repo.create(USER_ID, self.data)

    def test_all_lookups_bind_correct_user_ids_and_dates_and_preserve_missing_results(self) -> None:
        lookups: tuple[tuple[Callable[[], object], str, tuple[object, ...]], ...] = (
            (
                lambda: self.repo.get_by_id(MEASUREMENT_ID),
                QUERIES.body_measurements.get_by_id,
                (MEASUREMENT_ID,),
            ),
            (
                lambda: self.repo.get_by_user_and_id(USER_ID, MEASUREMENT_ID),
                QUERIES.body_measurements.get_by_user_and_id,
                (USER_ID, MEASUREMENT_ID),
            ),
            (
                lambda: self.repo.get_by_user_and_date(USER_ID, TODAY),
                QUERIES.body_measurements.get_by_user_and_date,
                (USER_ID, TODAY),
            ),
            (
                lambda: self.repo.get_latest_for_user(USER_ID),
                QUERIES.body_measurements.get_latest_for_user,
                (USER_ID,),
            ),
        )
        for operation, sql, params in lookups:
            for found in (True, False):
                with self.subTest(sql=sql, found=found):
                    self.fetch_one.reset_mock()
                    self.fetch_one.return_value = self.row if found else None
                    self.assertEqual(operation(), self.entry if found else None)
                    self.fetch_one.assert_called_once_with(sql, params)

    def test_listing_binds_each_filter_combination_and_pagination_boundaries(self) -> None:
        for lower, upper in (
            (None, None),
            (TODAY, None),
            (None, TODAY),
            (TODAY, TODAY),
            (TODAY, TODAY - timedelta(days=1)),
        ):
            for limit, offset, expected in ((100, 0, (100, 0)), (0, -1, (1, 0)), (1001, 5, (1000, 5))):
                with self.subTest(lower=lower, upper=upper, limit=limit, offset=offset):
                    self.fetch_all.reset_mock()
                    self.assertEqual(self.repo.list_by_user(USER_ID, limit, offset, lower, upper), [self.entry])
                    sql, params = self.fetch_all.call_args.args
                    bounds = tuple(value for value in (lower, upper) if value is not None)
                    self.assertEqual(params, (USER_ID, *bounds, *expected))
                    self.assertEqual(sql.count("%s"), len(params))
                    self.assertEqual("entry_date >= %s" in sql, lower is not None)
                    self.assertEqual("entry_date <= %s" in sql, upper is not None)
                    self.assertIn("ORDER BY entry_date DESC, id DESC", sql)

    def test_listing_can_return_empty_results(self) -> None:
        self.fetch_all.return_value = []
        self.assertEqual(self.repo.list_by_user(USER_ID), [])

    def test_each_update_field_is_allowed_and_scoped_to_user_and_id(self) -> None:
        for field in BodyMeasurementUpdate.model_fields:
            value = (
                TODAY + timedelta(days=1)
                if field == "entry_date"
                else ""
                if field == "notes"
                else Decimal("0.01")
            )
            data = BodyMeasurementUpdate.model_validate({field: value})
            with self.subTest(field=field):
                self.write.reset_mock()
                self.fetch_one.reset_mock()
                self.assertEqual(self.repo.update_owned(USER_ID, MEASUREMENT_ID, data), self.entry)
                sql, params = self.write.call_args.args
                self.assertIn(f"{field} = %s", sql)
                self.assertIn("WHERE user_id = %s AND id = %s", sql)
                self.assertEqual(params, (value, USER_ID, MEASUREMENT_ID))
                self.fetch_one.assert_called_once_with(
                    QUERIES.body_measurements.get_by_user_and_id, (USER_ID, MEASUREMENT_ID)
                )

    def test_empty_and_null_updates_only_read_current_owned_values(self) -> None:
        for data in (
            BodyMeasurementUpdate(),
            BodyMeasurementUpdate.model_validate(dict.fromkeys(BodyMeasurementUpdate.model_fields)),
        ):
            for found in (True, False):
                with self.subTest(data=data, found=found):
                    self.fetch_one.return_value = self.row if found else None
                    self.assertEqual(
                        self.repo.update_owned(USER_ID, MEASUREMENT_ID, data), self.entry if found else None
                    )
        self.write.assert_not_called()

    def test_unknown_update_fields_are_rejected_before_sql(self) -> None:
        data = Mock()
        data.model_dump.return_value = {"user_id": 999}
        with self.assertRaises(BodyMeasurementRepositoryError):
            self.repo.update_owned(USER_ID, MEASUREMENT_ID, data)
        self.write.assert_not_called()
        self.fetch_one.assert_not_called()

    def test_missing_update_readback_returns_none(self) -> None:
        self.fetch_one.return_value = None
        self.assertIsNone(
            self.repo.update_owned(USER_ID, MEASUREMENT_ID, BodyMeasurementUpdate(notes="changed"))
        )

    def test_delete_uses_user_scope_and_reports_affected_rows(self) -> None:
        for count in (0, 1, -1):
            with self.subTest(count=count):
                self.write.reset_mock()
                self.write.return_value = count
                self.assertEqual(self.repo.delete_owned(USER_ID, MEASUREMENT_ID), count > 0)
                self.write.assert_called_once_with(
                    QUERIES.body_measurements.delete_owned, (USER_ID, MEASUREMENT_ID)
                )

    def test_create_and_date_update_translate_only_the_known_constraint(self) -> None:
        new_date = TODAY + timedelta(days=1)
        for target, operation, expected_date in (
            (self.insert, lambda: self.repo.create(USER_ID, self.data), TODAY),
            (
                self.write,
                lambda: self.repo.update_owned(
                    USER_ID, MEASUREMENT_ID, BodyMeasurementUpdate(entry_date=new_date)
                ),
                new_date,
            ),
        ):
            failure = database_failure(unique_violation())
            target.side_effect = failure
            with (
                self.subTest(target=target),
                self.assertRaises(BodyMeasurementDateConflictRepositoryError) as raised,
            ):
                operation()
            self.assertEqual(raised.exception.entry_date, expected_date)
            self.assertIs(raised.exception.__cause__, failure)
            self.assertNotIn("private", str(raised.exception))
            target.side_effect = None
        self.fetch_one.assert_not_called()

    def test_unrelated_database_errors_remain_unchanged(self) -> None:
        for cause in (
            None,
            RuntimeError(DATE_CONSTRAINT),
            CheckViolation(DATE_CONSTRAINT),
            unique_violation("another_unique_key"),
            unique_violation(None),
        ):
            for target, operation in (
                (self.insert, lambda: self.repo.create(USER_ID, self.data)),
                (
                    self.write,
                    lambda: self.repo.update_owned(
                        USER_ID, MEASUREMENT_ID, BodyMeasurementUpdate(entry_date=TODAY)
                    ),
                ),
            ):
                failure = database_failure(cause)
                target.side_effect = failure
                with self.subTest(cause=cause, target=target), self.assertRaises(DatabaseError) as raised:
                    operation()
                self.assertIs(raised.exception, failure)
                target.side_effect = None

    def test_update_without_a_date_does_not_translate_a_constraint_failure(self) -> None:
        failure = database_failure(unique_violation())
        self.write.side_effect = failure
        with self.assertRaises(DatabaseError) as raised:
            self.repo.update_owned(USER_ID, MEASUREMENT_ID, BodyMeasurementUpdate(notes="changed"))
        self.assertIs(raised.exception, failure)

    def test_readback_failures_are_not_misclassified_as_write_conflicts(self) -> None:
        failure = database_failure(unique_violation())
        self.fetch_one.side_effect = failure
        for operation in (
            lambda: self.repo.create(USER_ID, self.data),
            lambda: self.repo.update_owned(USER_ID, MEASUREMENT_ID, BodyMeasurementUpdate(entry_date=TODAY)),
        ):
            with self.subTest(operation=operation), self.assertRaises(DatabaseError) as raised:
                operation()
            self.assertIs(raised.exception, failure)

    def test_invalid_rows_preserve_mapper_error(self) -> None:
        self.fetch_one.return_value = {**self.row, "waist": "bad"}
        for operation in (
            lambda: self.repo.get_by_id(MEASUREMENT_ID),
            lambda: self.repo.create(USER_ID, self.data),
        ):
            with self.subTest(operation=operation), self.assertRaises(BodyMeasurementRowError):
                operation()

    def test_actual_executor_preserves_driver_diagnostics_on_execute_and_commit_failures(self) -> None:
        for method in ("execute", "commit"):
            for operation, executor_name in (
                (lambda: self.repo.create(USER_ID, self.data), "execute_insert"),
                (
                    lambda: self.repo.update_owned(
                        USER_ID, MEASUREMENT_ID, BodyMeasurementUpdate(entry_date=TODAY)
                    ),
                    "execute_write",
                ),
            ):
                driver_error = unique_violation()
                connection = MagicMock()
                cursor = connection.cursor.return_value.__enter__.return_value
                connection.__enter__.return_value = connection
                cursor.fetchone.return_value = (MEASUREMENT_ID,)
                cursor.rowcount = 1
                getattr(cursor if method == "execute" else connection, method).side_effect = driver_error
                with (
                    self.subTest(method=method, executor=executor_name),
                    patch("data.executor.get_connection", return_value=connection),
                    patch("data.executor.logger"),
                    patch(
                        f"repositories.body_measurement_repository.{executor_name}",
                        getattr(executor, executor_name),
                    ),
                    self.assertRaises(BodyMeasurementDateConflictRepositoryError) as raised,
                ):
                    operation()
                cause = raised.exception.__cause__
                assert isinstance(cause, DatabaseError)
                self.assertIs(cause.__cause__, driver_error)
                if method == "execute":
                    connection.commit.assert_not_called()
