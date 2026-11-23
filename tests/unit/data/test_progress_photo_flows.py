"""Real progress-photo service/repository SQL flows against SQLite-backed rows.

A mocked psycopg connection adapts dates for the real executor. These tests cover
SQL behavior and competing-write outcomes, not PostgreSQL locking or isolation.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from functools import partial
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest import TestCase
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from core.errors.database import DatabaseError
from core.errors.progress_photo import ProgressPhotoNotFoundError
from repositories.progress_photo_repository import ProgressPhotoRepository
from schemas.progress_photo_schema import ProgressPhotoCreate, ProgressPhotoUpdate
from services.progress_photo_service import ProgressPhotoService
from tests.fixtures import TODAY, USER_ID, progress_photo

if TYPE_CHECKING:
    from collections.abc import Callable


class ProgressPhotoFlowTests(TestCase):
    def setUp(self) -> None:
        self.database = sqlite3.connect(":memory:")
        self.addCleanup(self.database.close)
        self.database.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE users (id INTEGER PRIMARY KEY);
            CREATE TABLE progress_photos (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                photo_url TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT '2026-10-01 12:00:00'
            );
        """)
        self.database.executemany("INSERT INTO users (id) VALUES (?)", [(USER_ID,), (USER_ID + 1,)])
        self.database.commit()
        self.before_write: Callable[[], None] | None = None
        self.writes: list[tuple[str, tuple[object, ...]]] = []
        self.enterContext(patch("data.executor.get_connection", side_effect=self._connection))
        self.enterContext(patch("data.executor.logger"))
        self.service = ProgressPhotoService(ProgressPhotoRepository())
        self.enterContext(patch.object(self.service, "logger"))

    def _connection(self) -> MagicMock:
        raw = self.database.cursor()
        cursor, connection = MagicMock(), MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value.__enter__.return_value = cursor
        connection.commit.side_effect = self.database.commit
        connection.rollback.side_effect = self.database.rollback
        names: list[str] = []

        def execute(sql: str, params: tuple[object, ...] = ()) -> None:
            nonlocal names
            if sql.lstrip().startswith(("INSERT", "UPDATE", "DELETE")):
                self.writes.append((sql, params))
                if self.before_write is not None:
                    callback, self.before_write = self.before_write, None
                    callback()
            converted = tuple(value.isoformat() if isinstance(value, date) else value for value in params)
            raw.execute(sql.replace("%s", "?"), converted)
            names = [str(column[0]) for column in raw.description or ()]
            cursor.description = [SimpleNamespace(name=name) for name in names] if names else None
            cursor.rowcount = raw.rowcount

        def values(row: tuple[object, ...]) -> tuple[object, ...]:
            result = list(row)
            for index, name in enumerate(names):
                value = result[index]
                if isinstance(value, str):
                    if name == "entry_date":
                        result[index] = date.fromisoformat(value)
                    elif name == "created_at":
                        result[index] = datetime.fromisoformat(value)
            return tuple(result)

        def fetch_one() -> tuple[object, ...] | None:
            row = raw.fetchone()
            return None if row is None else values(row)

        def close_connection(_type: object, _error: object, _traceback: object) -> None:
            if self.database.in_transaction:
                self.database.rollback()

        def close_cursor(_type: object, _error: object, _traceback: object) -> None:
            raw.close()

        cursor.execute.side_effect = execute
        cursor.fetchone.side_effect = fetch_one
        cursor.fetchall.side_effect = lambda: [values(row) for row in raw.fetchall()]
        connection.cursor.return_value.__exit__.side_effect = close_cursor
        connection.__exit__.side_effect = close_connection
        return connection

    def _data(self, day: date = TODAY, notes: str | None = "Front view") -> ProgressPhotoCreate:
        return ProgressPhotoCreate.model_validate(
            {**progress_photo().model_dump(), "entry_date": day, "notes": notes}
        )

    def test_complete_create_get_list_update_delete_flow(self) -> None:
        created = self.service.create(USER_ID, self._data())
        self.assertEqual(self.service.get_by_id(USER_ID, created.id), created)
        self.assertEqual(self.service.list_by_user(USER_ID), [created])
        updates = ProgressPhotoUpdate.model_validate(
            {"photo_url": "http://EXAMPLE.com", "entry_date": TODAY + timedelta(days=1), "notes": "Side view"}
        )
        updated = self.service.update(USER_ID, created.id, updates)
        self.assertEqual(str(updated.photo_url), "http://example.com/")
        self.assertEqual(updated.entry_date, TODAY + timedelta(days=1))
        self.assertEqual(updated.notes, "Side view")
        self.assertEqual(
            (updated.id, updated.user_id, updated.created_at), (created.id, USER_ID, created.created_at)
        )
        self.assertIsNone(self.service.delete(USER_ID, created.id))
        self.assertEqual(self.service.list_by_user(USER_ID), [])
        for operation in (
            partial(self.service.get_by_id, USER_ID, created.id),
            partial(self.service.update, USER_ID, created.id, ProgressPhotoUpdate()),
            partial(self.service.delete, USER_ID, created.id),
        ):
            with self.assertRaises(ProgressPhotoNotFoundError):
                operation()

    def test_duplicate_dates_and_urls_are_allowed_with_id_as_order_tiebreaker(self) -> None:
        self.assertEqual(self.service.list_by_user(USER_ID), [])
        first = self.service.create(USER_ID, self._data())
        second = self.service.create(USER_ID, self._data())
        newest = self.service.create(USER_ID, self._data(TODAY + timedelta(days=1)))
        self.service.create(USER_ID + 1, self._data())
        self.assertEqual(self.service.list_by_user(USER_ID), [newest, second, first])
        updated = self.service.update(USER_ID, first.id, ProgressPhotoUpdate(entry_date=newest.entry_date))
        self.assertEqual(self.service.list_by_user(USER_ID), [newest, updated, second])

    def test_inclusive_dates_reversed_ranges_and_pagination(self) -> None:
        old = self.service.create(USER_ID, self._data(TODAY - timedelta(days=1)))
        middle = self.service.create(USER_ID, self._data())
        new = self.service.create(USER_ID, self._data(TODAY + timedelta(days=1)))
        self.assertEqual(self.service.list_by_user(USER_ID, date_from=TODAY), [new, middle])
        self.assertEqual(self.service.list_by_user(USER_ID, date_to=TODAY), [middle, old])
        self.assertEqual(self.service.list_by_user(USER_ID, date_from=TODAY, date_to=TODAY), [middle])
        self.assertEqual(
            self.service.list_by_user(USER_ID, date_from=new.entry_date, date_to=old.entry_date), []
        )
        self.assertEqual(self.service.list_by_user(USER_ID, limit=1, offset=1), [middle])
        self.assertEqual(self.service.list_by_user(USER_ID, limit=0, offset=-1), [new])
        self.assertEqual(self.service.list_by_user(USER_ID, offset=9999), [])

    def test_other_users_and_missing_ids_cannot_read_update_or_delete_records(self) -> None:
        owned = self.service.create(USER_ID, self._data())
        self.assertEqual(self.service.list_by_user(USER_ID + 1), [])
        for photo_id in (owned.id, 999):
            operations: tuple[Callable[[], object], ...] = (
                partial(self.service.get_by_id, USER_ID + 1, photo_id),
                partial(self.service.update, USER_ID + 1, photo_id, ProgressPhotoUpdate(notes="Stolen")),
                partial(self.service.delete, USER_ID + 1, photo_id),
            )
            for operation in operations:
                with self.subTest(photo_id=photo_id, operation=operation):
                    self.writes.clear()
                    with self.assertRaises(ProgressPhotoNotFoundError):
                        operation()
                    self.assertEqual(self.writes, [])
        self.assertEqual(self.service.get_by_id(USER_ID, owned.id), owned)

    def test_empty_null_and_partial_updates_preserve_metadata(self) -> None:
        original = self.service.create(USER_ID, self._data())
        for updates in (
            ProgressPhotoUpdate(),
            ProgressPhotoUpdate(photo_url=None, entry_date=None, notes=None),
        ):
            with self.subTest(updates=updates):
                self.writes.clear()
                self.assertEqual(self.service.update(USER_ID, original.id, updates), original)
                self.assertEqual(self.writes, [])
        updated = self.service.update(USER_ID, original.id, ProgressPhotoUpdate(notes=""))
        self.assertEqual(updated.notes, "")
        self.assertEqual(self.service.update(USER_ID, original.id, ProgressPhotoUpdate(notes=None)), updated)
        self.assertEqual(
            (updated.photo_url, updated.entry_date, updated.created_at),
            (original.photo_url, original.entry_date, original.created_at),
        )

    def test_nullable_and_boundary_notes_roundtrip_and_are_bound_as_values(self) -> None:
        for notes in (None, "", "Фото", "x" * 1000, "O'Brien'); DROP TABLE users; --"):
            with self.subTest(notes=notes):
                created = self.service.create(USER_ID, self._data(notes=notes))
                self.assertEqual(created.notes, notes)
                sql, params = self.writes[-1]
                self.assertIn(notes, params)
                if notes:
                    self.assertNotIn(notes, sql)
        self.assertEqual(self.database.execute("SELECT COUNT(*) FROM users").fetchone()[0], 2)

    def test_disappearing_or_reassigned_records_do_not_affect_other_photos(self) -> None:
        survivor = self.service.create(USER_ID, self._data())
        for action in ("update", "delete"):
            for reassign in (False, True):
                with self.subTest(action=action, reassign=reassign):
                    photo = self.service.create(USER_ID, self._data())

                    def change_record(photo_id: int = photo.id, transfer: bool = reassign) -> None:
                        if transfer:
                            self.database.execute(
                                "UPDATE progress_photos SET user_id = ? WHERE id = ?", (USER_ID + 1, photo_id)
                            )
                        else:
                            self.database.execute("DELETE FROM progress_photos WHERE id = ?", (photo_id,))
                        self.database.commit()

                    self.before_write = change_record
                    with self.assertRaises(ProgressPhotoNotFoundError):
                        if action == "update":
                            self.service.update(USER_ID, photo.id, ProgressPhotoUpdate(notes="Changed"))
                        else:
                            self.service.delete(USER_ID, photo.id)
                    self.assertEqual(self.service.list_by_user(USER_ID), [survivor])
                    if reassign:
                        reassigned = self.service.get_by_id(USER_ID + 1, photo.id)
                        self.assertEqual(reassigned.notes, photo.notes)

    def test_user_deleted_before_insert_rejects_orphan_and_rolls_back(self) -> None:
        def remove_user() -> None:
            self.database.execute("DELETE FROM users WHERE id = ?", (USER_ID,))
            self.database.commit()

        self.before_write = remove_user
        with self.assertRaises(DatabaseError):
            self.service.create(USER_ID, self._data())
        self.assertFalse(self.database.in_transaction)
        self.assertEqual(self.database.execute("SELECT COUNT(*) FROM progress_photos").fetchone()[0], 0)

    def test_invalid_stored_url_is_a_validation_failure_instead_of_not_found(self) -> None:
        photo = self.service.create(USER_ID, self._data())
        self.database.execute(
            "UPDATE progress_photos SET photo_url = ? WHERE id = ?", ("ftp://example.com/p.jpg", photo.id)
        )
        self.database.commit()
        with self.assertRaises(ValidationError):
            self.service.get_by_id(USER_ID, photo.id)
        with self.assertRaises(ValidationError):
            self.service.list_by_user(USER_ID)
