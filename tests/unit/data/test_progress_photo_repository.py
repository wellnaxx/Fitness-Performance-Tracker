"""Progress-photo SQL binding, optional filters, partial changes, and error propagation."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest import TestCase
from unittest.mock import Mock, patch

from pydantic import ValidationError

from core.errors.database import DatabaseError
from core.errors.repository import ProgressPhotoRepositoryError, ProgressPhotoRowError
from data.queries import QUERIES
from repositories.progress_photo_repository import ProgressPhotoRepository
from schemas.progress_photo_schema import ProgressPhotoCreate, ProgressPhotoUpdate
from tests.fixtures import PHOTO_ID, TODAY, USER_ID, progress_photo

if TYPE_CHECKING:
    from collections.abc import Callable


class ProgressPhotoRepositoryTests(TestCase):
    def setUp(self) -> None:
        self.repo = ProgressPhotoRepository()
        self.photo = progress_photo()
        self.row: dict[str, object] = self.photo.model_dump(mode="python")
        self.row["photo_url"] = str(self.photo.photo_url)
        self.data = ProgressPhotoCreate.model_validate(self.photo.model_dump())
        self.fetch_one = self.enterContext(
            patch("repositories.progress_photo_repository.fetch_one", return_value=self.row)
        )
        self.fetch_all = self.enterContext(
            patch("repositories.progress_photo_repository.fetch_all", return_value=[self.row])
        )
        self.insert = self.enterContext(
            patch("repositories.progress_photo_repository.execute_insert", return_value=PHOTO_ID)
        )
        self.write = self.enterContext(
            patch("repositories.progress_photo_repository.execute_write", return_value=1)
        )
        self.logger = self.enterContext(patch("repositories.progress_photo_repository.logger"))

    def test_create_binds_url_as_text_and_reads_back_assigned_id(self) -> None:
        self.assertEqual(self.repo.create(USER_ID, self.data), self.photo)
        self.insert.assert_called_once_with(
            QUERIES.progress_photos.create, (USER_ID, str(self.data.photo_url), TODAY, "Front view")
        )
        self.fetch_one.assert_called_once_with(QUERIES.progress_photos.get_by_id, (PHOTO_ID,))

    def test_create_preserves_null_empty_and_sql_looking_notes_as_parameters(self) -> None:
        for notes in (None, "", "O'Brien'); DROP TABLE progress_photos; --", "x" * 1000):
            with self.subTest(notes=notes):
                self.insert.reset_mock()
                data = ProgressPhotoCreate.model_validate({**self.data.model_dump(), "notes": notes})
                self.repo.create(USER_ID, data)
                sql, params = self.insert.call_args.args
                self.assertEqual(params, (USER_ID, str(data.photo_url), TODAY, notes))
                self.assertEqual(sql.count("%s"), len(params))
                if notes:
                    self.assertNotIn(notes, sql)

    def test_missing_insert_readback_raises_repository_error_with_id_only_warning(self) -> None:
        self.fetch_one.return_value = None
        with self.assertRaises(ProgressPhotoRepositoryError):
            self.repo.create(USER_ID, self.data)
        self.logger.warning.assert_called_once_with(
            "Inserted row missing during readback | entity_id=%s", PHOTO_ID
        )

    def test_scoped_and_unscoped_lookups_bind_correct_ids_and_return_none_when_missing(self) -> None:
        for missing in (False, True):
            self.fetch_one.return_value = None if missing else self.row
            for lookup, sql, params in (
                (lambda: self.repo.get_by_id(PHOTO_ID), QUERIES.progress_photos.get_by_id, (PHOTO_ID,)),
                (
                    lambda: self.repo.get_by_user_and_id(USER_ID, PHOTO_ID),
                    QUERIES.progress_photos.get_by_user_and_id,
                    (USER_ID, PHOTO_ID),
                ),
            ):
                with self.subTest(missing=missing, params=params):
                    self.fetch_one.reset_mock()
                    self.assertEqual(lookup(), None if missing else self.photo)
                    self.fetch_one.assert_called_once_with(sql, params)

    def test_list_binds_all_date_combinations_and_preserves_empty_results(self) -> None:
        for lower, upper in (
            (None, None),
            (TODAY, None),
            (None, TODAY),
            (TODAY, TODAY),
            (TODAY, TODAY - timedelta(days=1)),
        ):
            for empty in (True, False):
                with self.subTest(lower=lower, upper=upper, empty=empty):
                    self.fetch_all.return_value = [] if empty else [self.row]
                    self.assertEqual(
                        self.repo.list_by_user(USER_ID, 3, 2, lower, upper), [] if empty else [self.photo]
                    )
                    sql, params = self.fetch_all.call_args.args
                    dates = tuple(value for value in (lower, upper) if value is not None)
                    self.assertEqual(params, (USER_ID, *dates, 3, 2))
                    self.assertEqual(sql.count("%s"), len(params))
                    self.assertEqual(QUERIES.progress_photos.filter_date_from in sql, lower is not None)
                    self.assertEqual(QUERIES.progress_photos.filter_date_to in sql, upper is not None)
                    self.assertIn("ORDER BY entry_date DESC, id DESC", sql)

    def test_list_uses_shared_defaults_and_clamps_limits_and_offsets(self) -> None:
        self.repo.list_by_user(USER_ID)
        self.assertEqual(self.fetch_all.call_args.args[1], (USER_ID, 100, 0))
        for limit, offset, normalized in (
            (0, -1, (1, 0)),
            (-2, 0, (1, 0)),
            (1001, 9999, (1000, 9999)),
            (1, 0, (1, 0)),
        ):
            with self.subTest(limit=limit, offset=offset):
                self.repo.list_by_user(USER_ID, limit, offset)
                self.assertEqual(self.fetch_all.call_args.args[1], (USER_ID, *normalized))

    def test_empty_and_all_null_updates_read_without_writing(self) -> None:
        for updates in (
            ProgressPhotoUpdate(),
            ProgressPhotoUpdate(photo_url=None, entry_date=None, notes=None),
        ):
            with self.subTest(updates=updates):
                self.fetch_one.reset_mock()
                self.assertEqual(self.repo.update_owned(USER_ID, PHOTO_ID, updates), self.photo)
                self.fetch_one.assert_called_once_with(
                    QUERIES.progress_photos.get_by_user_and_id, (USER_ID, PHOTO_ID)
                )
                self.write.assert_not_called()

    def test_update_binds_url_text_date_and_empty_notes_without_mutating_payload(self) -> None:
        day = TODAY + timedelta(days=1)
        data = ProgressPhotoUpdate.model_validate(
            {"photo_url": "https://EXAMPLE.com", "entry_date": day, "notes": ""}
        )
        original = data.model_dump()
        self.assertEqual(self.repo.update_owned(USER_ID, PHOTO_ID, data), self.photo)
        sql, params = self.write.call_args.args
        self.assertEqual(params, ("https://example.com/", day, "", USER_ID, PHOTO_ID))
        self.assertEqual(sql.count("%s"), len(params))
        self.assertIn("photo_url = %s, entry_date = %s, notes = %s", sql)
        self.assertEqual(data.model_dump(), original)

    def test_partial_update_skips_nulls_and_only_writes_requested_fields(self) -> None:
        data = ProgressPhotoUpdate(photo_url=None, notes="Changed")
        self.repo.update_owned(USER_ID, PHOTO_ID, data)
        sql, params = self.write.call_args.args
        self.assertEqual(params, ("Changed", USER_ID, PHOTO_ID))
        self.assertIn("SET notes = %s", sql)
        self.assertNotIn("photo_url =", sql)

    def test_unsupported_update_fields_cannot_change_owner_or_structure_sql(self) -> None:
        for field in ("user_id", "id", "created_at", "notes = NULL; --"):
            with self.subTest(field=field):
                data = Mock(spec=ProgressPhotoUpdate)
                data.model_dump.return_value = {field: "private value"}
                with self.assertRaises(ProgressPhotoRepositoryError):
                    self.repo.update_owned(USER_ID, PHOTO_ID, data)
                self.write.assert_not_called()

    def test_update_missing_readback_returns_none(self) -> None:
        self.fetch_one.return_value = None
        self.assertIsNone(self.repo.update_owned(USER_ID, PHOTO_ID, ProgressPhotoUpdate(notes="Changed")))

    def test_delete_binds_owned_id_and_reports_affected_rows(self) -> None:
        for affected in (0, 1):
            with self.subTest(affected=affected):
                self.write.reset_mock()
                self.write.return_value = affected
                self.assertEqual(self.repo.delete_owned(USER_ID, PHOTO_ID), bool(affected))
                self.write.assert_called_once_with(QUERIES.progress_photos.delete_owned, (USER_ID, PHOTO_ID))

    def test_executor_failures_propagate_without_masking_original_errors(self) -> None:
        cases: tuple[tuple[str, Callable[[], object]], ...] = (
            ("execute_insert", lambda: self.repo.create(USER_ID, self.data)),
            ("fetch_one", lambda: self.repo.get_by_user_and_id(USER_ID, PHOTO_ID)),
            ("fetch_all", lambda: self.repo.list_by_user(USER_ID)),
            (
                "execute_write",
                lambda: self.repo.update_owned(USER_ID, PHOTO_ID, ProgressPhotoUpdate(notes="Changed")),
            ),
            ("execute_write", lambda: self.repo.delete_owned(USER_ID, PHOTO_ID)),
        )
        for executor, operation in cases:
            failure = DatabaseError("private database failure")
            with (
                self.subTest(operation=operation),
                patch(f"repositories.progress_photo_repository.{executor}", side_effect=failure),
            ):
                with self.assertRaises(DatabaseError) as raised:
                    operation()
                self.assertIs(raised.exception, failure)

    def test_invalid_rows_raise_type_or_schema_errors(self) -> None:
        cases: tuple[tuple[dict[str, object], type[Exception]], ...] = (
            ({**self.row, "user_id": "invalid"}, ProgressPhotoRowError),
            ({**self.row, "photo_url": "ftp://example.com/p.jpg"}, ValidationError),
        )
        for row, error in cases:
            with self.subTest(error=error):
                self.fetch_one.return_value = row
                self.fetch_all.return_value = [row]
                for operation in (
                    lambda: self.repo.get_by_id(PHOTO_ID),
                    lambda: self.repo.list_by_user(USER_ID),
                ):
                    with self.assertRaises(error):
                        operation()
