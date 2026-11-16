"""Real body weight service/repository/executor queries against portable stored rows.

SQLite enforces user/date uniqueness. A mocked psycopg connection adapts values
and supplies real PostgreSQL diagnostics for uniqueness failures. These tests
exercise competing-write outcomes, not PostgreSQL isolation or real concurrency.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.errors.body_weight_entry import BodyWeightEntryDateConflictError, BodyWeightEntryNotFoundError
from repositories.body_weight_entry_repository import BodyWeightEntryRepository
from schemas.body_weight_entry_schema import BodyWeightEntryCreate, BodyWeightEntryUpdate
from services.body_weight_entry_service import BodyWeightEntryService
from tests.fixtures import TODAY, USER_ID
from tests.unit.data.test_body_weight_entry_repository import unique_violation

if TYPE_CHECKING:
    from collections.abc import Callable


class BodyWeightEntryFlowTests(TestCase):
    def setUp(self) -> None:
        self.database = sqlite3.connect(":memory:")
        self.addCleanup(self.database.close)
        self.database.executescript("""
            CREATE TABLE body_weight_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                weight NUMERIC NOT NULL CHECK (weight > 0),
                entry_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, entry_date)
            );
        """)
        self.before_write: Callable[[], None] | None = None
        self.service = BodyWeightEntryService(BodyWeightEntryRepository())
        self.enterContext(patch.object(self.service, "logger"))
        self.enterContext(patch("data.executor.logger"))
        self.enterContext(patch("data.executor.get_connection", side_effect=self.open_connection))

    def open_connection(self) -> MagicMock:
        """Adapt a cursor while preserving the shared executor's commit/error behavior."""
        raw = self.database.cursor()
        cursor = MagicMock()
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value.__enter__.return_value = cursor
        connection.commit.side_effect = self.database.commit
        names: list[str] = []

        def execute(sql: str, params: tuple[object, ...] = ()) -> None:
            nonlocal names
            if sql.startswith(("INSERT", "UPDATE", "DELETE")) and self.before_write is not None:
                callback, self.before_write = self.before_write, None
                callback()
            converted = tuple(
                value.isoformat()
                if isinstance(value, date)
                else str(value)
                if isinstance(value, Decimal)
                else value
                for value in params
            )
            try:
                raw.execute(sql.replace("%s", "?"), converted)
            except sqlite3.IntegrityError as exc:
                if exc.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE:
                    raise unique_violation() from exc
                raise
            names = [str(column[0]) for column in raw.description or ()]
            cursor.description = [SimpleNamespace(name=name) for name in names] if names else None
            cursor.rowcount = raw.rowcount

        def values(row: tuple[object, ...]) -> tuple[object, ...]:
            result = list(row)
            for index, name in enumerate(names):
                value = result[index]
                if name == "entry_date" and isinstance(value, str):
                    result[index] = date.fromisoformat(value)
                elif name == "created_at" and isinstance(value, str):
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

    def create(self, day: date = TODAY, user_id: int = USER_ID) -> int:
        """Create a minimally valid entry and return its database-assigned ID."""
        return self.service.create(user_id, BodyWeightEntryCreate(entry_date=day, weight=Decimal("75.5"))).id

    def competing_insert(self, day: date) -> None:
        """Commit a winning write between the service's date check and its mutation."""
        self.database.execute(
            "INSERT INTO body_weight_entries (user_id, entry_date, weight) VALUES (?, ?, ?)",
            (USER_ID, day.isoformat(), "85"),
        )
        self.database.commit()

    def test_complete_create_lookup_update_and_delete_flow(self) -> None:
        entry_id = self.create()
        entry = self.service.get_by_id(USER_ID, entry_id)
        self.assertEqual(self.service.get_by_date(USER_ID, TODAY), entry)
        self.assertEqual(self.service.get_latest(USER_ID), entry)
        new_date = TODAY + timedelta(days=1)
        updated = self.service.update(
            USER_ID, entry_id, BodyWeightEntryUpdate(entry_date=new_date, weight=Decimal("76.25"))
        )
        self.assertEqual(updated.entry_date, new_date)
        self.assertEqual(updated.weight, Decimal("76.25"))
        self.assertEqual(updated.created_at, entry.created_at)
        self.assertEqual(self.service.get_by_date(USER_ID, new_date), updated)
        with self.assertRaises(BodyWeightEntryNotFoundError):
            self.service.get_by_date(USER_ID, TODAY)
        self.service.delete(USER_ID, entry_id)
        self.assertEqual(self.service.list_by_user(USER_ID), [])
        for lookup in (
            lambda: self.service.get_by_id(USER_ID, entry_id),
            lambda: self.service.get_latest(USER_ID),
            lambda: self.service.delete(USER_ID, entry_id),
        ):
            with self.subTest(lookup=lookup), self.assertRaises(BodyWeightEntryNotFoundError):
                lookup()

    def test_users_can_share_dates_but_cannot_access_or_mutate_each_others_entries(self) -> None:
        own_id = self.create()
        other_id = self.create(user_id=99)
        self.assertNotEqual(own_id, other_id)
        self.assertEqual([entry.id for entry in self.service.list_by_user(USER_ID)], [own_id])
        self.assertEqual(self.service.get_by_date(99, TODAY).id, other_id)
        for operation in (
            lambda: self.service.get_by_id(USER_ID, other_id),
            lambda: self.service.update(
                USER_ID, other_id, BodyWeightEntryUpdate(entry_date=TODAY + timedelta(days=1))
            ),
            lambda: self.service.delete(USER_ID, other_id),
        ):
            with self.subTest(operation=operation), self.assertRaises(BodyWeightEntryNotFoundError):
                operation()
        self.assertEqual(self.service.get_by_id(99, other_id).user_id, 99)
        with self.assertRaises(BodyWeightEntryDateConflictError):
            self.create()
        self.assertEqual(len(self.service.list_by_user(USER_ID)), 1)

    def test_changed_date_conflicts_preserve_both_rows_and_same_date_is_valid(self) -> None:
        first_id = self.create()
        next_date = TODAY + timedelta(days=1)
        second_id = self.create(next_date)
        before = self.service.list_by_user(USER_ID)
        with self.assertRaises(BodyWeightEntryDateConflictError):
            self.service.update(
                USER_ID, first_id, BodyWeightEntryUpdate(entry_date=next_date, weight=Decimal("90"))
            )
        self.assertEqual(self.service.list_by_user(USER_ID), before)
        updated = self.service.update(
            USER_ID, second_id, BodyWeightEntryUpdate(entry_date=next_date, weight=Decimal("90"))
        )
        self.assertEqual(updated.weight, Decimal("90"))
        self.assertEqual(updated.entry_date, next_date)

    def test_competing_create_returns_conflict_and_leaves_only_the_winning_entry(self) -> None:
        self.before_write = lambda: self.competing_insert(TODAY)
        with self.assertRaises(BodyWeightEntryDateConflictError) as raised:
            self.create()
        self.assertIsNotNone(raised.exception.__cause__)
        entries = self.service.list_by_user(USER_ID)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].weight, Decimal("85"))
        self.create(TODAY + timedelta(days=1))
        self.assertEqual(len(self.service.list_by_user(USER_ID)), 2)

    def test_competing_date_change_rolls_back_the_losing_update(self) -> None:
        entry_id = self.create()
        before = self.service.get_by_id(USER_ID, entry_id)
        new_date = TODAY + timedelta(days=1)
        self.before_write = lambda: self.competing_insert(new_date)
        with self.assertRaises(BodyWeightEntryDateConflictError):
            self.service.update(
                USER_ID, entry_id, BodyWeightEntryUpdate(entry_date=new_date, weight=Decimal("99"))
            )
        self.assertEqual(self.service.get_by_id(USER_ID, entry_id), before)
        self.assertEqual(self.service.get_by_date(USER_ID, new_date).weight, Decimal("85"))

    def test_listing_filters_order_pagination_and_latest_use_entry_dates(self) -> None:
        dates = (TODAY + timedelta(days=2), TODAY, TODAY + timedelta(days=1))
        ids = {day: self.create(day) for day in dates}
        self.create(TODAY + timedelta(days=9), user_id=99)
        self.assertEqual(
            [entry.id for entry in self.service.list_by_user(USER_ID)],
            [ids[day] for day in sorted(dates, reverse=True)],
        )
        self.assertEqual(self.service.get_latest(USER_ID).entry_date, max(dates))
        for lower, upper, expected_dates in (
            (TODAY, TODAY, [TODAY]),
            (TODAY + timedelta(days=1), None, [max(dates), TODAY + timedelta(days=1)]),
            (None, TODAY, [TODAY]),
            (max(dates), TODAY, []),
            (TODAY + timedelta(days=10), None, []),
        ):
            with self.subTest(lower=lower, upper=upper):
                entries = self.service.list_by_user(USER_ID, date_from=lower, date_to=upper)
                self.assertEqual([entry.entry_date for entry in entries], expected_dates)
        self.assertEqual(self.service.list_by_user(USER_ID, offset=1000), [])
        self.assertEqual(
            self.service.list_by_user(USER_ID, limit=1, offset=1)[0].entry_date, TODAY + timedelta(days=1)
        )
        self.assertEqual(len(self.service.list_by_user(USER_ID, limit=0, offset=-1)), 1)

    def test_partial_empty_and_null_updates_preserve_weight_and_date(self) -> None:
        entry_id = self.create()
        before = self.service.get_by_id(USER_ID, entry_id)
        for data in (BodyWeightEntryUpdate(), BodyWeightEntryUpdate(weight=None, entry_date=None)):
            self.assertEqual(self.service.update(USER_ID, entry_id, data), before)
        updated = self.service.update(USER_ID, entry_id, BodyWeightEntryUpdate(weight=Decimal("0.01")))
        self.assertEqual(updated.weight, Decimal("0.01"))
        self.assertEqual(updated.entry_date, TODAY)
        self.assertEqual(updated.created_at, before.created_at)

    def test_deleted_dates_can_be_reused_and_all_storable_weight_boundaries_round_trip(self) -> None:
        for value in (Decimal("0.01"), Decimal("75.50"), Decimal("999.99")):
            with self.subTest(weight=value):
                entry = self.service.create(USER_ID, BodyWeightEntryCreate(entry_date=TODAY, weight=value))
                self.assertEqual(self.service.get_by_date(USER_ID, TODAY).weight, value)
                self.service.delete(USER_ID, entry.id)
                self.assertEqual(self.service.list_by_user(USER_ID), [])
