"""Meal-item service/repository SQL flows using SQLite and a mocked psycopg connection.

These exercise SQL binding, parent scoping, and disappearing-row outcomes without
a running PostgreSQL server. They do not verify PostgreSQL locking or isolation.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from decimal import Decimal
from functools import partial
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.errors.database import DatabaseError
from core.errors.meal import MealNotFoundError
from core.errors.meal_item import MealItemNotFoundError
from repositories.meal_item_repository import MealItemRepository
from repositories.meal_repository import MealRepository
from schemas.meal_item_schema import MealItemCreate, MealItemUpdate
from services.meal_item_service import MealItemService
from tests.fixtures import MEAL_ID, USER_ID, meal_item

if TYPE_CHECKING:
    from collections.abc import Callable


class MealItemFlowTests(TestCase):
    def setUp(self) -> None:
        self.database = sqlite3.connect(":memory:")
        self.addCleanup(self.database.close)
        self.database.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE meals (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL DEFAULT 'Lunch',
                description TEXT,
                eaten_at TEXT NOT NULL DEFAULT '2026-10-01 12:00:00',
                meal_type TEXT NOT NULL DEFAULT 'lunch',
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT '2026-10-01 12:00:00',
                updated_at TEXT NOT NULL DEFAULT '2026-10-01 12:00:00'
            );
            CREATE TABLE meal_items (
                id INTEGER PRIMARY KEY,
                meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                serving_size TEXT,
                calories TEXT NOT NULL,
                protein TEXT NOT NULL,
                carbs TEXT NOT NULL,
                fats TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT '2026-10-01 12:00:00'
            );
        """)
        self.database.executemany(
            "INSERT INTO meals (id, user_id) VALUES (?, ?)",
            [(MEAL_ID, USER_ID), (MEAL_ID + 1, USER_ID), (MEAL_ID + 2, USER_ID + 1)],
        )
        self.database.commit()
        self.before_write: Callable[[], None] | None = None
        self.writes: list[tuple[str, tuple[object, ...]]] = []
        self.enterContext(patch("data.executor.get_connection", side_effect=self._connection))
        self.enterContext(patch("services.meal_item_service.logging.getLogger"))
        self.enterContext(patch("data.executor.logger"))
        self.service = MealItemService(MealRepository(), MealItemRepository())

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
            converted = tuple(str(value) if isinstance(value, Decimal) else value for value in params)
            raw.execute(sql.replace("%s", "?"), converted)
            names = [str(column[0]) for column in raw.description or ()]
            cursor.description = [SimpleNamespace(name=name) for name in names] if names else None
            cursor.rowcount = raw.rowcount

        def values(row: tuple[object, ...]) -> tuple[object, ...]:
            result = list(row)
            for index, name in enumerate(names):
                value = result[index]
                if isinstance(value, str):
                    if name in {"created_at", "updated_at", "eaten_at"}:
                        result[index] = datetime.fromisoformat(value)
                    elif name in {"serving_size", "calories", "protein", "carbs", "fats"}:
                        result[index] = Decimal(value)
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

    def _data(self, meal_id: int = MEAL_ID, name: str = "Oats") -> MealItemCreate:
        return MealItemCreate.model_validate({**meal_item().model_dump(), "meal_id": meal_id, "name": name})

    def test_complete_create_get_list_update_delete_flow(self) -> None:
        created = self.service.create(USER_ID, self._data())
        self.assertEqual(self.service.get_by_id(USER_ID, MEAL_ID, created.id), created)
        self.assertEqual(self.service.list_by_meal(USER_ID, MEAL_ID), [created])
        updated = self.service.update(
            USER_ID,
            MEAL_ID,
            created.id,
            MealItemUpdate(
                name="Rice",
                serving_size=Decimal("0"),
                calories=Decimal("0"),
                protein=Decimal("0.01"),
                carbs=Decimal("25.50"),
                fats=Decimal("0"),
            ),
        )
        self.assertEqual(updated.name, "Rice")
        self.assertEqual(updated.serving_size, Decimal("0"))
        self.assertEqual(updated.calories, Decimal("0"))
        self.assertEqual(updated.protein, Decimal("0.01"))
        self.assertEqual(updated.carbs, Decimal("25.50"))
        self.assertEqual(updated.fats, Decimal("0"))
        self.assertEqual(
            (updated.id, updated.meal_id, updated.created_at), (created.id, MEAL_ID, created.created_at)
        )
        self.assertIsNone(self.service.delete(USER_ID, MEAL_ID, created.id))
        self.assertEqual(self.service.list_by_meal(USER_ID, MEAL_ID), [])
        with self.assertRaises(MealItemNotFoundError):
            self.service.get_by_id(USER_ID, MEAL_ID, created.id)
        with self.assertRaises(MealItemNotFoundError):
            self.service.delete(USER_ID, MEAL_ID, created.id)
        with self.assertRaises(MealItemNotFoundError):
            self.service.update(USER_ID, MEAL_ID, created.id, MealItemUpdate(name="Missing"))

    def test_list_is_empty_then_ascending_id_with_duplicate_names_allowed(self) -> None:
        self.assertEqual(self.service.list_by_meal(USER_ID, MEAL_ID), [])
        first = self.service.create(USER_ID, self._data(name="Zucchini"))
        second = self.service.create(USER_ID, self._data(name="Apple"))
        third = self.service.create(USER_ID, self._data(name="Apple"))
        self.service.create(USER_ID, self._data(meal_id=MEAL_ID + 1))
        self.assertEqual(self.service.list_by_meal(USER_ID, MEAL_ID), [first, second, third])

    def test_missing_and_foreign_parents_block_all_operations_without_writes(self) -> None:
        foreign = self.service.create(USER_ID + 1, self._data(meal_id=MEAL_ID + 2))
        for parent in (MEAL_ID + 2, 999):
            operations: tuple[Callable[[], object], ...] = (
                partial(self.service.create, USER_ID, self._data(meal_id=parent)),
                partial(self.service.get_by_id, USER_ID, parent, foreign.id),
                partial(self.service.list_by_meal, USER_ID, parent),
                partial(self.service.update, USER_ID, parent, foreign.id, MealItemUpdate(name="Stolen")),
                partial(self.service.delete, USER_ID, parent, foreign.id),
            )
            for operation in operations:
                with self.subTest(parent=parent, operation=operation):
                    self.writes.clear()
                    with self.assertRaises(MealNotFoundError):
                        operation()
                    self.assertEqual(self.writes, [])
        self.assertEqual(self.service.get_by_id(USER_ID + 1, foreign.meal_id, foreign.id), foreign)

    def test_wrong_meal_blocks_get_update_delete_even_when_both_meals_are_owned(self) -> None:
        item = self.service.create(USER_ID, self._data())
        operations: tuple[Callable[[], object], ...] = (
            lambda: self.service.get_by_id(USER_ID, MEAL_ID + 1, item.id),
            lambda: self.service.update(USER_ID, MEAL_ID + 1, item.id, MealItemUpdate(name="Moved")),
            lambda: self.service.delete(USER_ID, MEAL_ID + 1, item.id),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                self.writes.clear()
                with self.assertRaises(MealItemNotFoundError):
                    operation()
                self.assertEqual(self.writes, [])
        self.assertEqual(self.service.get_by_id(USER_ID, MEAL_ID, item.id), item)

    def test_empty_and_all_null_updates_preserve_values_without_sql_writes(self) -> None:
        item = self.service.create(USER_ID, self._data())
        for updates in (
            MealItemUpdate(),
            MealItemUpdate.model_validate(dict.fromkeys(MealItemUpdate.model_fields)),
        ):
            with self.subTest(fields=updates.model_fields_set):
                self.writes.clear()
                self.assertEqual(self.service.update(USER_ID, MEAL_ID, item.id, updates), item)
                self.assertEqual(self.writes, [])

    def test_partial_changes_preserve_other_fields_and_null_does_not_clear_serving_size(self) -> None:
        item = self.service.create(USER_ID, self._data())
        updates: dict[str, object] = {
            "name": "A",
            "serving_size": Decimal("0"),
            "calories": Decimal("0"),
            "protein": Decimal("0"),
            "carbs": Decimal("0"),
            "fats": Decimal("0"),
        }
        for field, value in updates.items():
            with self.subTest(field=field):
                changed = self.service.update(
                    USER_ID, MEAL_ID, item.id, MealItemUpdate.model_validate({field: value})
                )
                self.assertEqual(changed.model_dump(), {**item.model_dump(), field: value})
                item = changed
        changed = self.service.update(USER_ID, MEAL_ID, item.id, MealItemUpdate(serving_size=None, name="Rice"))
        self.assertEqual(changed.serving_size, Decimal("0"))
        self.assertEqual(changed.name, "Rice")

    def test_names_are_bound_as_values_and_never_interpreted_as_sql(self) -> None:
        name = "Oats'); DROP TABLE meals; --"
        created = self.service.create(USER_ID, self._data(name=name))
        self.assertEqual(created.name, name)
        self.assertNotIn(name, self.writes[-1][0])
        self.assertIn(name, self.writes[-1][1])
        changed = self.service.update(USER_ID, MEAL_ID, created.id, MealItemUpdate(name="x' OR '1'='1"))
        self.assertEqual(changed.name, "x' OR '1'='1")
        self.assertEqual(self.database.execute("SELECT COUNT(*) FROM meals").fetchone()[0], 3)

    def test_item_disappearing_before_update_or_delete_does_not_affect_other_items(self) -> None:
        survivor = self.service.create(USER_ID, self._data())
        for action in ("update", "delete"):
            with self.subTest(action=action):
                item = self.service.create(USER_ID, self._data())

                def remove_item(item_id: int = item.id) -> None:
                    self.database.execute("DELETE FROM meal_items WHERE id = ?", (item_id,))
                    self.database.commit()

                self.before_write = remove_item
                with self.assertRaises(MealItemNotFoundError):
                    if action == "update":
                        self.service.update(USER_ID, MEAL_ID, item.id, MealItemUpdate(name="Gone"))
                    else:
                        self.service.delete(USER_ID, MEAL_ID, item.id)
                self.assertEqual(self.service.list_by_meal(USER_ID, MEAL_ID), [survivor])

    def test_parent_deleted_after_ownership_check_rejects_insert_without_orphan_rows(self) -> None:
        def remove_parent() -> None:
            self.database.execute("DELETE FROM meals WHERE id = ?", (MEAL_ID,))
            self.database.commit()

        self.before_write = remove_parent
        with self.assertRaises(DatabaseError):
            self.service.create(USER_ID, self._data())
        self.assertFalse(self.database.in_transaction)
        self.assertEqual(self.database.execute("SELECT COUNT(*) FROM meal_items").fetchone()[0], 0)
