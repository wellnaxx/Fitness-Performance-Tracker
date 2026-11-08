"""Real service/repository SQL flows through a mocked PostgreSQL cursor.

SQLite stores fixture rows and exercises commit/rollback and portable SQL.
The adapter supplies PostgreSQL-style values and removes FOR UPDATE for SQLite;
these tests verify lock issuance, not PostgreSQL locking or isolation behavior.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, create_autospec, patch

from psycopg import OperationalError

from core.errors.database import DatabaseError
from core.errors.repository import SetEntryRepositoryError, SetEntryRowError
from core.errors.set_entry import SetEntryCreationError, SetEntryNotFoundError, SetEntryValidationError
from core.errors.workout_exercise import WorkoutExerciseNotFoundError
from data.executor import QueryExecutor
from data.queries import QUERIES
from data.unit_of_work import PostgresUnitOfWork
from ports.repositories.workout_exercise_repository import WorkoutExerciseRepositoryPort
from ports.repositories.workout_repository import WorkoutRepositoryPort
from repositories.set_entry_repository import SetEntryRepository
from schemas.set_entry_schema import SetEntryCreate, SetEntryUpdate
from services.set_entry_service import SetEntryService
from tests.fixtures import ENTRY_ID, SET_ENTRY_ID, USER_ID, WORKOUT_ID, entry, workout


class SetEntryTransactionTests(TestCase):
    def setUp(self) -> None:
        self.database = sqlite3.connect(":memory:")
        self.addCleanup(self.database.close)
        self.database.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE workout_exercises (id INTEGER PRIMARY KEY);
            INSERT INTO workout_exercises VALUES (17), (29);
            CREATE TABLE set_entries (
                id INTEGER PRIMARY KEY,
                workout_exercise_id INTEGER REFERENCES workout_exercises(id) ON DELETE CASCADE,
                set_number INTEGER NOT NULL CHECK (set_number > 0),
                reps INTEGER NOT NULL CHECK (reps >= 0),
                weight REAL NOT NULL CHECK (weight >= 0),
                rpe INTEGER,
                is_warmup INTEGER NOT NULL DEFAULT 0,
                completed INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT '2026-10-01 12:00:00'
            );
        """)
        self.seed(5)
        self.connections: list[MagicMock] = []
        self.writes = 0
        self.fail_write_number: int | None = None
        self.write_failure = OperationalError("injected write failure")
        self.commit_failure = OperationalError("injected commit failure")
        self.fail_commit = False
        self.missing_readback = False
        self.corrupt_readback = False
        self.read_executor = create_autospec(QueryExecutor, instance=True, spec_set=True)
        self.read_executor.fetch_one.side_effect = self.read_one
        self.read_executor.fetch_all.side_effect = self.read_all
        self.read_executor.execute_write.side_effect = AssertionError("Write outside transaction")
        self.read_executor.execute_insert.side_effect = AssertionError("Insert outside transaction")
        self.sets = SetEntryRepository(self.read_executor)
        self.exercises = create_autospec(WorkoutExerciseRepositoryPort, instance=True, spec_set=True)
        self.exercises.get_by_id.return_value = entry()
        self.workouts = create_autospec(WorkoutRepositoryPort, instance=True, spec_set=True)
        self.workouts.get_by_user_and_id.return_value = workout()
        self.uow = PostgresUnitOfWork()
        self.service = SetEntryService(self.sets, self.exercises, self.workouts, self.uow)
        self.enterContext(patch("data.unit_of_work.get_connection", side_effect=self.open_connection))
        self.enterContext(
            patch("data.executor.get_connection", side_effect=AssertionError("Standalone connection"))
        )
        self.enterContext(patch("data.unit_of_work.logger"))

    def seed(self, count: int) -> None:
        self.database.execute("DELETE FROM set_entries")
        self.database.executemany(
            "INSERT INTO set_entries (id, workout_exercise_id, set_number, reps, weight, rpe) "
            "VALUES (?, ?, ?, 5, 20, 7)",
            [(SET_ENTRY_ID + index, ENTRY_ID, index + 1) for index in range(count)] + [(91, 29, 3)],
        )
        self.database.commit()

    def values(self, raw: tuple[object, ...], names: list[str]) -> tuple[object, ...]:
        result = dict(zip(names, raw, strict=True))
        for name in ("is_warmup", "completed"):
            if name in result:
                result[name] = bool(result[name])
        if isinstance(result.get("created_at"), str):
            result["created_at"] = datetime.fromisoformat(str(result["created_at"]))
        return tuple(result.values())

    def read_all(self, sql: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
        cursor = self.database.execute(sql.replace("%s", "?"), params)
        try:
            names = [str(column[0]) for column in cursor.description or ()]
            return [dict(zip(names, self.values(row, names), strict=True)) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def read_one(self, sql: str, params: tuple[object, ...] = ()) -> dict[str, object] | None:
        rows = self.read_all(sql, params)
        return rows[0] if rows else None

    def open_connection(self) -> MagicMock:
        self.database.execute("BEGIN")
        raw_cursor = self.database.cursor()
        cursor = MagicMock(spec_set=("execute", "fetchone", "fetchall", "description", "rowcount", "close"))
        conn = MagicMock(spec_set=("cursor", "commit", "rollback", "close"))
        conn.cursor.return_value = cursor
        names: list[str] = []
        last_sql = ""
        self.writes = 0

        def execute(sql: str, params: tuple[object, ...] = ()) -> None:
            nonlocal names, last_sql
            last_sql = sql
            if sql.startswith(("UPDATE", "INSERT", "DELETE", "WITH")):
                self.writes += 1
                if self.writes == self.fail_write_number:
                    raise self.write_failure
            raw_cursor.execute(sql.replace("FOR UPDATE;", ";").replace("%s", "?"), params)
            names = [str(column[0]) for column in raw_cursor.description or ()]
            cursor.description = [SimpleNamespace(name=name) for name in names] if names else None
            cursor.rowcount = raw_cursor.rowcount

        def fetch_one() -> tuple[object, ...] | None:
            raw = raw_cursor.fetchone()
            if raw is None or (self.missing_readback and self.writes and last_sql.startswith("SELECT")):
                return None
            result = self.values(raw, names)
            if self.corrupt_readback and self.writes and "reps" in names:
                fields = dict(zip(names, result, strict=True))
                fields["reps"] = "invalid"
                return tuple(fields.values())
            return result

        def commit() -> None:
            if self.fail_commit:
                raise self.commit_failure
            self.database.commit()

        def close() -> None:
            if self.database.in_transaction:
                self.database.rollback()

        cursor.execute.side_effect = execute
        cursor.fetchone.side_effect = fetch_one
        cursor.fetchall.side_effect = lambda: [self.values(row, names) for row in raw_cursor.fetchall()]
        cursor.close.side_effect = raw_cursor.close
        conn.commit.side_effect = commit
        conn.rollback.side_effect = self.database.rollback
        conn.close.side_effect = close
        self.connections.append(conn)
        return conn

    def snapshot(self) -> list[tuple[object, ...]]:
        return [tuple(row) for row in self.database.execute("SELECT * FROM set_entries ORDER BY id")]

    def ordered_ids(self) -> list[int]:
        return [
            int(row[0])
            for row in self.database.execute(
                "SELECT id FROM set_entries WHERE workout_exercise_id = ? ORDER BY set_number, id", (ENTRY_ID,)
            )
        ]

    def assert_transaction(self, committed: bool) -> None:
        conn = self.connections[-1]
        conn.cursor.assert_called_once_with()
        self.assertEqual(
            conn.cursor.return_value.execute.call_args_list[0].args,
            (QUERIES.set_entries.lock_for_workout_exercise, (ENTRY_ID,)),
        )
        self.assertEqual(conn.rollback.call_count, int(not committed))
        if committed:
            conn.commit.assert_called_once_with()
        conn.cursor.return_value.close.assert_called_once_with()
        conn.close.assert_called_once_with()
        with self.assertRaises(DatabaseError):
            _ = self.uow.set_entry

    def test_complete_create_read_list_update_delete_flow_preserves_order(self) -> None:
        before = self.snapshot()
        created = self.service.create(
            USER_ID, SetEntryCreate(workout_exercise_id=ENTRY_ID, set_number=3, reps=8, weight=30)
        )
        self.assertEqual(self.service.get_by_id(USER_ID, created.id), created)
        self.assertEqual(len(self.service.list_by_workout_exercise(USER_ID, ENTRY_ID)), 6)
        updated = self.service.update(USER_ID, ENTRY_ID, created.id, SetEntryUpdate(set_number=1, reps=0))
        self.assertEqual((updated.set_number, updated.reps), (1, 0))
        self.service.delete(USER_ID, ENTRY_ID, created.id)
        self.assertEqual(self.snapshot(), before)
        for conn in self.connections:
            conn.commit.assert_called_once_with()
            conn.rollback.assert_not_called()

    def test_create_at_every_valid_position_including_empty_and_append(self) -> None:
        for count in (0, 1, 3, 5):
            for position in range(1, count + 2):
                with self.subTest(count=count, position=position):
                    self.seed(count)
                    created = self.service.create(
                        USER_ID,
                        SetEntryCreate(workout_exercise_id=ENTRY_ID, set_number=position, reps=0, weight=0),
                    )
                    expected = list(range(SET_ENTRY_ID, SET_ENTRY_ID + count))
                    expected.insert(position - 1, created.id)
                    self.assertEqual(self.ordered_ids(), expected)
                    self.assertEqual(
                        [
                            record.set_number
                            for record in self.service.list_by_workout_exercise(USER_ID, ENTRY_ID)
                        ],
                        list(range(1, count + 2)),
                    )
                    self.assert_transaction(committed=True)

    def test_every_reorder_preserves_all_other_sets_and_consecutive_numbers(self) -> None:
        for old in range(1, 6):
            for new in range(1, 6):
                if old == new:
                    continue
                with self.subTest(old=old, new=new):
                    self.seed(5)
                    target = SET_ENTRY_ID + old - 1
                    updated = self.service.update(USER_ID, ENTRY_ID, target, SetEntryUpdate(set_number=new))
                    expected = list(range(SET_ENTRY_ID, SET_ENTRY_ID + 5))
                    expected.insert(new - 1, expected.pop(old - 1))
                    self.assertEqual(self.ordered_ids(), expected)
                    self.assertEqual(updated.set_number, new)
                    self.assertEqual(
                        [
                            record.set_number
                            for record in self.service.list_by_workout_exercise(USER_ID, ENTRY_ID)
                        ],
                        [1, 2, 3, 4, 5],
                    )
                    self.assertEqual(
                        self.database.execute("SELECT set_number FROM set_entries WHERE id = 91").fetchone(),
                        (3,),
                    )
                    self.assert_transaction(committed=True)

    def test_delete_every_position_including_final_set_normalizes_remaining_numbers(self) -> None:
        for count in (1, 3, 5):
            for position in range(1, count + 1):
                with self.subTest(count=count, position=position):
                    self.seed(count)
                    target = SET_ENTRY_ID + position - 1
                    self.service.delete(USER_ID, ENTRY_ID, target)
                    expected = list(range(SET_ENTRY_ID, SET_ENTRY_ID + count))
                    expected.remove(target)
                    self.assertEqual(self.ordered_ids(), expected)
                    records = self.service.list_by_workout_exercise(USER_ID, ENTRY_ID)
                    self.assertEqual([record.set_number for record in records], list(range(1, count)))
                    self.assert_transaction(committed=True)

    def test_delete_then_append_does_not_duplicate_an_existing_position(self) -> None:
        self.seed(3)
        self.service.delete(USER_ID, ENTRY_ID, SET_ENTRY_ID + 1)
        self.service.create(
            USER_ID, SetEntryCreate(workout_exercise_id=ENTRY_ID, set_number=3, reps=5, weight=10)
        )
        self.assertEqual(
            [record.set_number for record in self.service.list_by_workout_exercise(USER_ID, ENTRY_ID)],
            [1, 2, 3],
        )

    def test_partial_updates_keep_none_fields_and_apply_zero_and_false(self) -> None:
        self.database.execute("UPDATE set_entries SET is_warmup = 1 WHERE id = ?", (SET_ENTRY_ID,))
        self.database.commit()
        updates = SetEntryUpdate(reps=0, weight=0, rpe=None, is_warmup=False, completed=False)
        updated = self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, updates)
        self.assertEqual(
            (updated.reps, updated.weight, updated.rpe, updated.is_warmup, updated.completed),
            (0, 0, 7, False, False),
        )
        self.assert_transaction(committed=True)

    def test_empty_and_none_only_updates_return_existing_values(self) -> None:
        original = self.service.get_by_id(USER_ID, SET_ENTRY_ID)
        for updates in (SetEntryUpdate(), SetEntryUpdate(rpe=None)):
            with self.subTest(updates=updates):
                self.assertEqual(self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, updates), original)
                self.assertEqual(self.writes, 0)
                self.assert_transaction(committed=True)

    def test_invalid_or_unchanged_positions_roll_back_without_changes(self) -> None:
        before = self.snapshot()
        operations = (
            lambda: self.service.create(
                USER_ID, SetEntryCreate(workout_exercise_id=ENTRY_ID, set_number=7, reps=0, weight=0)
            ),
            lambda: self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate(set_number=6)),
            lambda: self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate(set_number=1, reps=8)),
        )
        for operation in operations:
            with self.subTest(operation=operation), self.assertRaises(SetEntryValidationError):
                operation()
            self.assertEqual(self.snapshot(), before)
            self.assert_transaction(committed=False)

    def test_failed_second_write_rolls_back_insert_update_and_delete_ordering(self) -> None:
        before = self.snapshot()
        self.fail_write_number = 2
        operations = (
            lambda: self.service.create(
                USER_ID, SetEntryCreate(workout_exercise_id=ENTRY_ID, set_number=2, reps=5, weight=10)
            ),
            lambda: self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate(set_number=5)),
            lambda: self.service.delete(USER_ID, ENTRY_ID, SET_ENTRY_ID),
        )
        for operation in operations:
            with self.subTest(operation=operation), self.assertRaises(DatabaseError):
                operation()
            self.assertEqual(self.snapshot(), before)
            self.connections[-1].commit.assert_not_called()
            self.assert_transaction(committed=False)

    def test_missing_readback_rolls_back_creation_and_update(self) -> None:
        before = self.snapshot()
        self.missing_readback = True
        with self.assertRaises(SetEntryCreationError):
            self.service.create(
                USER_ID, SetEntryCreate(workout_exercise_id=ENTRY_ID, set_number=2, reps=5, weight=10)
            )
        self.assertEqual(self.snapshot(), before)
        self.assert_transaction(committed=False)
        with self.assertRaises(SetEntryNotFoundError):
            self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate(set_number=5))
        self.assertEqual(self.snapshot(), before)
        self.assert_transaction(committed=False)

    def test_invalid_mapping_rolls_back_all_prior_changes(self) -> None:
        before = self.snapshot()
        self.corrupt_readback = True
        operations = (
            lambda: self.service.create(
                USER_ID, SetEntryCreate(workout_exercise_id=ENTRY_ID, set_number=2, reps=5, weight=10)
            ),
            lambda: self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate(set_number=5)),
        )
        for operation in operations:
            with self.subTest(operation=operation), self.assertRaises(SetEntryRowError):
                operation()
            self.assertEqual(self.snapshot(), before)
            self.assert_transaction(committed=False)

    def test_commit_failure_rolls_back_all_mutations(self) -> None:
        before = self.snapshot()
        self.fail_commit = True
        operations = (
            lambda: self.service.create(
                USER_ID, SetEntryCreate(workout_exercise_id=ENTRY_ID, set_number=2, reps=5, weight=10)
            ),
            lambda: self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate(set_number=5)),
            lambda: self.service.delete(USER_ID, ENTRY_ID, SET_ENTRY_ID),
        )
        for operation in operations:
            with self.subTest(operation=operation), self.assertRaises(DatabaseError):
                operation()
            self.assertEqual(self.snapshot(), before)
            self.connections[-1].commit.assert_called_once_with()
            self.assert_transaction(committed=False)

    def test_parent_disappearing_before_lock_prevents_writes(self) -> None:
        def delete_parent(user_id: int, workout_id: int) -> object:
            self.assertEqual((user_id, workout_id), (USER_ID, WORKOUT_ID))
            self.database.execute("DELETE FROM workout_exercises WHERE id = ?", (ENTRY_ID,))
            self.database.commit()
            return workout()

        self.workouts.get_by_user_and_id.side_effect = delete_parent
        with self.assertRaises(WorkoutExerciseNotFoundError):
            self.service.create(
                USER_ID, SetEntryCreate(workout_exercise_id=ENTRY_ID, set_number=1, reps=0, weight=0)
            )
        self.assertEqual(self.writes, 0)
        self.assert_transaction(committed=False)

    def test_scoped_repository_reads_and_delete_do_not_touch_another_exercise(self) -> None:
        self.assertIsNone(self.sets.get_by_workout_exercise_and_id(29, SET_ENTRY_ID))
        before = self.snapshot()
        with self.uow as uow:
            self.assertFalse(uow.set_entry.delete_in_workout_exercise(29, SET_ENTRY_ID))
        self.assertEqual(self.snapshot(), before)

    def test_unsupported_update_fields_are_rejected_before_execution(self) -> None:
        with (
            patch.object(SetEntryUpdate, "model_dump", return_value={"id = 1; --": "bad"}),
            self.assertRaises(SetEntryRepositoryError),
        ):
            self.sets.update_in_workout_exercise(ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate())
        self.read_executor.execute_write.assert_not_called()
