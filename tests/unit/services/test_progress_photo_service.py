"""Progress-photo ownership, CRUD, payload preservation, and failure boundaries."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING
from unittest import TestCase
from unittest.mock import call, create_autospec, patch

from core.errors.database import DatabaseError
from core.errors.progress_photo import (
    ProgressPhotoCreationError,
    ProgressPhotoDeleteError,
    ProgressPhotoNotFoundError,
    ProgressPhotoUpdateError,
)
from core.errors.repository import ProgressPhotoRepositoryError, ProgressPhotoRowError
from ports.repositories.progress_photo_repository import ProgressPhotoRepositoryPort
from schemas.progress_photo_schema import ProgressPhotoCreate, ProgressPhotoUpdate
from services.progress_photo_service import ProgressPhotoService
from tests.fixtures import PHOTO_ID, TODAY, USER_ID, progress_photo
from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.errors.base import ServiceError
    from schemas.progress_photo_schema import ProgressPhotoPublic


class ProgressPhotoServiceTests(TestCase):
    def setUp(self) -> None:
        self.repo = create_autospec(ProgressPhotoRepositoryPort, instance=True, spec_set=True)
        self.service = ProgressPhotoService(self.repo)
        self.logger = self.enterContext(patch.object(self.service, "logger"))
        self.photo = progress_photo()
        self.data = ProgressPhotoCreate.model_validate(self.photo.model_dump())
        self.updates = ProgressPhotoUpdate(notes="Changed")
        self.repo.create.return_value = self.photo
        self.repo.get_by_user_and_id.return_value = self.photo
        self.repo.list_by_user.return_value = [self.photo]
        self.repo.update_owned.return_value = self.photo
        self.repo.delete_owned.return_value = True

    def test_create_uses_authenticated_owner_and_returns_persisted_record(self) -> None:
        self.assertIs(self.service.create(USER_ID, self.data), self.photo)
        self.assertEqual(self.repo.mock_calls, [call.create(USER_ID, self.data)])
        self.logger.info.assert_called_once_with(
            "Progress photo created | user_id=%s photo_id=%s", USER_ID, PHOTO_ID
        )

    def test_create_preserves_valid_urls_date_boundaries_and_optional_notes(self) -> None:
        for url in ("http://example.com", "https://EXAMPLE.com/front.jpg?size=large#view"):
            for day in (date.min, date(2024, 2, 29), TODAY, date.max):
                for notes in (None, "", "Фото спереду", "x" * 1000):
                    with self.subTest(url=url, day=day, notes_length=None if notes is None else len(notes)):
                        self.repo.reset_mock()
                        data = ProgressPhotoCreate.model_validate(
                            {"photo_url": url, "entry_date": day, "notes": notes}
                        )
                        original = data.model_dump()
                        self.service.create(USER_ID, data)
                        self.repo.create.assert_called_once_with(USER_ID, data)
                        self.assertEqual(data.model_dump(), original)

    def test_create_allows_repeated_dates_and_urls(self) -> None:
        second = self.photo.model_copy(update={"id": PHOTO_ID + 1})
        self.repo.create.side_effect = (self.photo, second)
        self.assertIs(self.service.create(USER_ID, self.data), self.photo)
        self.assertIs(self.service.create(USER_ID, self.data), second)
        self.assertEqual(self.repo.mock_calls, [call.create(USER_ID, self.data)] * 2)

    def test_get_uses_owned_lookup_without_unscoped_access(self) -> None:
        self.assertIs(self.service.get_by_id(USER_ID, PHOTO_ID), self.photo)
        self.assertEqual(self.repo.mock_calls, [call.get_by_user_and_id(USER_ID, PHOTO_ID)])
        self.repo.get_by_id.assert_not_called()
        self.logger.debug.assert_called_once()
        self.logger.info.assert_not_called()

    def test_missing_or_foreign_records_block_get_update_and_delete(self) -> None:
        self.repo.get_by_user_and_id.return_value = None
        operations: tuple[Callable[[], object], ...] = (
            lambda: self.service.get_by_id(USER_ID, PHOTO_ID),
            lambda: self.service.update(USER_ID, PHOTO_ID, self.updates),
            lambda: self.service.delete(USER_ID, PHOTO_ID),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                self.repo.reset_mock()
                self.logger.reset_mock()
                with self.assertRaises(ProgressPhotoNotFoundError) as raised:
                    operation()
                self.assertEqual(str(raised.exception), str(ProgressPhotoNotFoundError.not_found(PHOTO_ID)))
                self.assertEqual(self.repo.mock_calls, [call.get_by_user_and_id(USER_ID, PHOTO_ID)])
                self.logger.warning.assert_called_once()
                self.logger.info.assert_not_called()

    def test_list_preserves_empty_single_multiple_and_repository_order(self) -> None:
        second = self.photo.model_copy(update={"id": PHOTO_ID + 1})
        cases: tuple[list[ProgressPhotoPublic], ...] = ([], [self.photo], [second, self.photo])
        for photos in cases:
            with self.subTest(count=len(photos)):
                self.repo.reset_mock()
                self.logger.reset_mock()
                self.repo.list_by_user.return_value = photos
                self.assertIs(self.service.list_by_user(USER_ID), photos)
                self.assertEqual(
                    self.repo.mock_calls,
                    [call.list_by_user(USER_ID, DEFAULT_LIMIT, DEFAULT_OFFSET, None, None)],
                )
                self.logger.debug.assert_called_once()
                self.logger.info.assert_not_called()

    def test_list_forwards_pagination_and_all_date_filters_without_altering_them(self) -> None:
        for lower, upper in (
            (None, None),
            (TODAY, None),
            (None, TODAY),
            (TODAY, TODAY),
            (TODAY, TODAY - timedelta(days=1)),
        ):
            for limit, offset in ((1, 0), (1000, 2), (1001, 9999), (0, -1)):
                with self.subTest(lower=lower, upper=upper, limit=limit, offset=offset):
                    self.repo.reset_mock()
                    self.service.list_by_user(USER_ID, limit, offset, lower, upper)
                    self.repo.list_by_user.assert_called_once_with(USER_ID, limit, offset, lower, upper)
                    self.repo.get_by_id.assert_not_called()

    def test_update_checks_ownership_before_writing_and_returns_readback(self) -> None:
        expected = self.photo.model_copy(update={"notes": "Changed"})
        self.repo.update_owned.return_value = expected
        self.assertIs(self.service.update(USER_ID, PHOTO_ID, self.updates), expected)
        self.assertEqual(
            self.repo.mock_calls,
            [call.get_by_user_and_id(USER_ID, PHOTO_ID), call.update_owned(USER_ID, PHOTO_ID, self.updates)],
        )
        self.logger.info.assert_called_once()

    def test_update_accepts_each_field_full_empty_null_and_unchanged_payloads(self) -> None:
        payloads: tuple[dict[str, object], ...] = (
            {},
            {"photo_url": None, "entry_date": None, "notes": None},
            {"photo_url": str(self.photo.photo_url)},
            {"entry_date": TODAY},
            {"photo_url": "http://example.com/new.jpg"},
            {"entry_date": TODAY + timedelta(days=1)},
            {"notes": ""},
            {"notes": "x" * 1000},
            {"notes": None, "entry_date": TODAY},
            {
                "photo_url": "https://example.com/new.jpg",
                "entry_date": TODAY + timedelta(days=1),
                "notes": "New",
            },
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                self.repo.reset_mock()
                updates = ProgressPhotoUpdate.model_validate(payload)
                original = updates.model_dump()
                self.assertIs(self.service.update(USER_ID, PHOTO_ID, updates), self.photo)
                self.repo.get_by_user_and_id.assert_called_once_with(USER_ID, PHOTO_ID)
                self.repo.update_owned.assert_called_once_with(USER_ID, PHOTO_ID, updates)
                self.assertEqual(updates.model_dump(), original)

    def test_update_disappearing_record_is_not_found_without_success_logging(self) -> None:
        self.repo.update_owned.return_value = None
        with self.assertRaises(ProgressPhotoNotFoundError) as raised:
            self.service.update(USER_ID, PHOTO_ID, self.updates)
        self.assertEqual(str(raised.exception), str(ProgressPhotoNotFoundError.not_accessible(PHOTO_ID)))
        self.logger.warning.assert_called_once()
        self.logger.info.assert_not_called()

    def test_delete_checks_ownership_and_deletes_only_the_record(self) -> None:
        self.assertIsNone(self.service.delete(USER_ID, PHOTO_ID))
        self.assertEqual(
            self.repo.mock_calls,
            [call.get_by_user_and_id(USER_ID, PHOTO_ID), call.delete_owned(USER_ID, PHOTO_ID)],
        )
        self.logger.info.assert_called_once()

    def test_delete_disappearing_record_uses_deletion_warning_and_not_found(self) -> None:
        self.repo.delete_owned.return_value = False
        with self.assertRaises(ProgressPhotoNotFoundError) as raised:
            self.service.delete(USER_ID, PHOTO_ID)
        self.assertEqual(str(raised.exception), str(ProgressPhotoNotFoundError.not_accessible(PHOTO_ID)))
        self.logger.warning.assert_called_once_with(
            "Progress photo deletion affected no row | user_id=%s photo_id=%s", USER_ID, PHOTO_ID
        )
        self.logger.info.assert_not_called()

    def test_missing_delete_warning_refers_to_deletion(self) -> None:
        self.repo.get_by_user_and_id.return_value = None
        with self.assertRaises(ProgressPhotoNotFoundError):
            self.service.delete(USER_ID, PHOTO_ID)
        self.logger.warning.assert_called_once_with(
            "Progress photo not found during deletion | user_id=%s photo_id=%s", USER_ID, PHOTO_ID
        )

    def test_repository_write_failures_have_safe_errors_and_preserve_original_causes(self) -> None:
        cases: tuple[tuple[str, Callable[[], object], type[ServiceError]], ...] = (
            ("create", lambda: self.service.create(USER_ID, self.data), ProgressPhotoCreationError),
            (
                "update_owned",
                lambda: self.service.update(USER_ID, PHOTO_ID, self.updates),
                ProgressPhotoUpdateError,
            ),
            ("delete_owned", lambda: self.service.delete(USER_ID, PHOTO_ID), ProgressPhotoDeleteError),
        )
        for method, operation, expected in cases:
            failure = ProgressPhotoRepositoryError("private SQL and photo URL")
            with self.subTest(method=method), patch.object(self.repo, method, side_effect=failure):
                self.logger.reset_mock()
                with self.assertRaises(expected) as raised:
                    operation()
                self.assertIs(raised.exception.__cause__, failure)
                self.assertNotIn("private", str(raised.exception))
                self.logger.exception.assert_called_once()
                self.logger.info.assert_not_called()

    def test_lookup_failures_propagate_without_mutations_or_success_logs(self) -> None:
        cases: tuple[tuple[str, Callable[[], object]], ...] = (
            ("get_by_user_and_id", lambda: self.service.get_by_id(USER_ID, PHOTO_ID)),
            ("list_by_user", lambda: self.service.list_by_user(USER_ID)),
            ("get_by_user_and_id", lambda: self.service.update(USER_ID, PHOTO_ID, self.updates)),
            ("get_by_user_and_id", lambda: self.service.delete(USER_ID, PHOTO_ID)),
        )
        for method, operation in cases:
            for error in (
                DatabaseError("database error"),
                ProgressPhotoRepositoryError("repository error"),
                ProgressPhotoRowError("invalid row"),
                RuntimeError("unexpected error"),
            ):
                with (
                    self.subTest(method=method, error=type(error).__name__),
                    patch.object(self.repo, method, side_effect=error),
                ):
                    self.repo.reset_mock()
                    self.logger.reset_mock()
                    with self.assertRaises(type(error)) as raised:
                        operation()
                    self.assertIs(raised.exception, error)
                    self.repo.create.assert_not_called()
                    self.repo.update_owned.assert_not_called()
                    self.repo.delete_owned.assert_not_called()
                    self.logger.info.assert_not_called()

    def test_database_mapping_and_unexpected_write_errors_keep_original_types(self) -> None:
        cases: tuple[tuple[str, Callable[[], object]], ...] = (
            ("create", lambda: self.service.create(USER_ID, self.data)),
            ("update_owned", lambda: self.service.update(USER_ID, PHOTO_ID, self.updates)),
            ("delete_owned", lambda: self.service.delete(USER_ID, PHOTO_ID)),
        )
        for method, operation in cases:
            for error in (
                DatabaseError("database error"),
                ProgressPhotoRowError("invalid row"),
                RuntimeError("unexpected error"),
            ):
                with (
                    self.subTest(method=method, error=type(error).__name__),
                    patch.object(self.repo, method, side_effect=error),
                ):
                    self.logger.reset_mock()
                    with self.assertRaises(type(error)) as raised:
                        operation()
                    self.assertIs(raised.exception, error)
                    self.logger.info.assert_not_called()
