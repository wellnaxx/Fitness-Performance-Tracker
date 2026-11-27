"""Atomic ordering SQL flows; SQLite checks rollback, not PostgreSQL row locking."""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, create_autospec, patch

from psycopg import OperationalError

from core.errors.database import DatabaseError
from core.errors.exercise import ExerciseNotFoundError
from core.errors.repository import WorkoutExerciseRepositoryError
from core.errors.workout import WorkoutNotFoundError
from core.errors.workout_exercise import (
    WorkoutExerciseCreationError,
    WorkoutExerciseDeleteError,
    WorkoutExerciseNotFoundError,
    WorkoutExerciseUpdateError,
    WorkoutExerciseValidationError,
)
from data.executor import QueryExecutor
from data.unit_of_work import PostgresUnitOfWork
from repositories.user_repository import UserRepository
from repositories.workout_exercise_repository import WorkoutExerciseRepository
from repositories.workout_repository import WorkoutRepository
from schemas.workout_exercises_schema import WorkoutExerciseCreate, WorkoutExerciseUpdate
from services.workout_exercise_service import WorkoutExerciseService
from tests.fixtures import ENTRY_ID, EXERCISE_ID, USER_ID, WORKOUT_ID, entry


class WorkoutExerciseTransactionTests(TestCase):
    def setUp(self) -> None:
        self.database = sqlite3.connect(":memory:")
        self.addCleanup(self.database.close)
        self.database.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE workouts (id INTEGER PRIMARY KEY, user_id INTEGER);
            INSERT INTO workouts VALUES (11, 7), (29, 8), (30, NULL);
            CREATE TABLE exercises (id INTEGER PRIMARY KEY, created_by INTEGER);
            INSERT INTO exercises VALUES (13, NULL), (19, 7), (23, 8);
            CREATE TABLE workout_exercises (
                id INTEGER PRIMARY KEY,
                workout_id INTEGER NOT NULL REFERENCES workouts(id),
                exercise_id INTEGER NOT NULL REFERENCES exercises(id),
                order_index INTEGER NOT NULL CHECK (order_index >= 0),
                rest_seconds INTEGER CHECK (rest_seconds >= 0),
                notes TEXT
            );
        """)
        self.seed(5)
        self.connections: list[MagicMock] = []
        self.writes = 0
        self.fail_write: int | None = None
        self.missing_readback = False
        self.invalid_readback = False
        self.fail_commit = False
        self.failure = OperationalError("injected statement failure")
        self.uow = PostgresUnitOfWork()
        self.service = WorkoutExerciseService(WorkoutExerciseRepository(), WorkoutRepository(), self.uow)
        self.enterContext(patch("data.unit_of_work.get_connection", side_effect=self.open_connection))
        self.enterContext(patch("data.executor.get_connection", side_effect=AssertionError("Standalone query")))
        self.logger = self.enterContext(patch.object(self.service, "logger"))
        self.enterContext(patch.object(self.uow, "logger"))

    def seed(self, count: int) -> None:
        self.database.execute("DELETE FROM workout_exercises")
        self.database.executemany(
            "INSERT INTO workout_exercises VALUES (?, ?, ?, ?, ?, ?)",
            [(ENTRY_ID + i, WORKOUT_ID, EXERCISE_ID, i, 60, "Original") for i in range(count)]
            + [(91, 29, EXERCISE_ID, 3, 45, "Other workout")],
        )
        self.database.commit()

    def open_connection(self) -> MagicMock:
        self.database.execute("BEGIN")
        raw_cursor = self.database.cursor()
        cursor = MagicMock(spec_set=("execute", "fetchone", "fetchall", "description", "rowcount", "close"))
        conn = MagicMock(spec_set=("cursor", "commit", "rollback", "close"))
        conn.cursor.return_value = cursor
        self.writes = 0
        names: list[str] = []

        def execute(sql: str, params: tuple[object, ...] = ()) -> None:
            nonlocal names
            if sql.startswith(("UPDATE", "INSERT", "DELETE", "WITH")):
                self.writes += 1
                if self.writes == self.fail_write:
                    raise self.failure
            sqlite_sql = sql.replace("FOR UPDATE;", ";").replace("FOR SHARE;", ";").replace("%s", "?")
            raw_cursor.execute(sqlite_sql, params)
            names = [str(column[0]) for column in raw_cursor.description or ()]
            cursor.description = [SimpleNamespace(name=name) for name in names] if names else None
            cursor.rowcount = raw_cursor.rowcount

        def fetch_one() -> tuple[object, ...] | None:
            row: tuple[object, ...] | None = raw_cursor.fetchone()
            if row is not None and self.writes and "order_index" in names:
                if self.missing_readback:
                    return None
                if self.invalid_readback:
                    fields = dict(zip(names, row, strict=True))
                    fields["order_index"] = "invalid"
                    return tuple(fields.values())
            return row

        def commit() -> None:
            if self.fail_commit:
                raise self.failure
            self.database.commit()

        cursor.execute.side_effect = execute
        cursor.fetchone.side_effect = fetch_one
        cursor.fetchall.side_effect = raw_cursor.fetchall
        cursor.close.side_effect = raw_cursor.close
        conn.commit.side_effect = commit
        conn.rollback.side_effect = self.database.rollback
        conn.close.side_effect = lambda: self.database.rollback() if self.database.in_transaction else None
        self.connections.append(conn)
        return conn

    def snapshot(self) -> list[tuple[object, ...]]:
        return self.database.execute("SELECT * FROM workout_exercises ORDER BY id").fetchall()

    def ordered_ids(self) -> list[int]:
        return [
            row[0]
            for row in self.database.execute(
                "SELECT id FROM workout_exercises WHERE workout_id = ? ORDER BY order_index, id", (WORKOUT_ID,)
            )
        ]

    def assert_contiguous(self, expected_ids: list[int]) -> None:
        self.assertEqual(self.ordered_ids(), expected_ids)
        self.assertEqual(
            self.database.execute(
                "SELECT order_index FROM workout_exercises WHERE workout_id = ? ORDER BY order_index",
                (WORKOUT_ID,),
            ).fetchall(),
            [(index,) for index in range(len(expected_ids))],
        )
        self.assertEqual(
            self.database.execute("SELECT order_index, notes FROM workout_exercises WHERE id = 91").fetchone(),
            (3, "Other workout"),
        )

    def assert_committed(self) -> None:
        conn = self.connections[-1]
        conn.commit.assert_called_once_with()
        conn.rollback.assert_not_called()
        conn.cursor.assert_called_once_with()
        conn.cursor.return_value.close.assert_called_once_with()
        conn.close.assert_called_once_with()

    def assert_rolled_back(self, before: list[tuple[object, ...]]) -> None:
        conn = self.connections[-1]
        conn.rollback.assert_called_once_with()
        conn.close.assert_called_once_with()
        self.assertEqual(self.snapshot(), before)
        self.logger.info.assert_not_called()

    def test_create_at_every_position_in_empty_and_nonempty_workouts(self) -> None:
        for count in (0, 1, 4):
            for position in range(count + 1):
                with self.subTest(count=count, position=position):
                    self.seed(count)
                    expected = self.ordered_ids()
                    data = WorkoutExerciseCreate(
                        exercise_id=19, order_index=position, rest_seconds=0, notes="New"
                    )
                    created = self.service.create(USER_ID, WORKOUT_ID, data)
                    expected.insert(position, created.id)
                    self.assert_contiguous(expected)
                    self.assertEqual((created.exercise_id, created.rest_seconds, created.notes), (19, 0, "New"))
                    self.assert_committed()

    def test_update_moves_every_entry_to_every_position_in_both_directions(self) -> None:
        for old in range(5):
            for new in range(5):
                with self.subTest(old=old, new=new):
                    self.seed(5)
                    expected = self.ordered_ids()
                    target = expected.pop(old)
                    expected.insert(new, target)
                    updated = self.service.update(
                        USER_ID, WORKOUT_ID, target, WorkoutExerciseUpdate(order_index=new, notes="Moved")
                    )
                    self.assertEqual((updated.id, updated.order_index, updated.notes), (target, new, "Moved"))
                    self.assert_contiguous(expected)
                    self.assertEqual(self.writes, 1 if old == new else 2)
                    self.assert_committed()

    def test_delete_first_middle_last_and_only_entry(self) -> None:
        for count in (1, 5):
            for position in range(count):
                with self.subTest(count=count, position=position):
                    self.seed(count)
                    expected = self.ordered_ids()
                    target = expected.pop(position)
                    self.service.delete(USER_ID, WORKOUT_ID, target)
                    self.assert_contiguous(expected)
                    self.assert_committed()

    def test_empty_null_and_nonposition_updates_preserve_order_and_falsey_values(self) -> None:
        for updates in (
            WorkoutExerciseUpdate(),
            WorkoutExerciseUpdate(notes=None, order_index=None),
            WorkoutExerciseUpdate(rest_seconds=0, notes=""),
            WorkoutExerciseUpdate(exercise_id=19),
        ):
            with self.subTest(updates=updates):
                self.seed(3)
                result = self.service.update(USER_ID, WORKOUT_ID, ENTRY_ID, updates)
                self.assert_contiguous([ENTRY_ID + i for i in range(3)])
                if updates.rest_seconds is not None:
                    self.assertEqual((result.rest_seconds, result.notes), (0, ""))
                if updates.exercise_id is not None:
                    self.assertEqual(result.exercise_id, 19)
                self.assert_committed()

    def test_missing_foreign_and_global_workouts_abort_without_writes(self) -> None:
        before = self.snapshot()
        for parent in (29, 30, 999):
            for operation in (
                lambda parent=parent: self.service.create(
                    USER_ID, parent, WorkoutExerciseCreate(exercise_id=13, order_index=0)
                ),
                lambda parent=parent: self.service.update(
                    USER_ID, parent, ENTRY_ID, WorkoutExerciseUpdate(notes="No")
                ),
                lambda parent=parent: self.service.delete(USER_ID, parent, ENTRY_ID),
            ):
                with self.subTest(parent=parent), self.assertRaises(WorkoutNotFoundError):
                    operation()
                self.assertEqual(self.writes, 0)
                self.assert_rolled_back(before)

    def test_missing_and_foreign_catalog_exercises_abort_creation_and_replacement(self) -> None:
        before = self.snapshot()
        for exercise_id in (23, 999):
            for operation in (
                lambda exercise_id=exercise_id: self.service.create(
                    USER_ID, WORKOUT_ID, WorkoutExerciseCreate(exercise_id=exercise_id, order_index=0)
                ),
                lambda exercise_id=exercise_id: self.service.update(
                    USER_ID, WORKOUT_ID, ENTRY_ID, WorkoutExerciseUpdate(exercise_id=exercise_id, order_index=3)
                ),
            ):
                with self.subTest(exercise_id=exercise_id), self.assertRaises(ExerciseNotFoundError):
                    operation()
                self.assertEqual(self.writes, 0)
                self.assert_rolled_back(before)

    def test_missing_and_wrong_workout_entries_abort_update_and_delete(self) -> None:
        before = self.snapshot()
        for target in (91, 999):
            for operation in (
                lambda target=target: self.service.update(
                    USER_ID, WORKOUT_ID, target, WorkoutExerciseUpdate(order_index=1)
                ),
                lambda target=target: self.service.delete(USER_ID, WORKOUT_ID, target),
            ):
                with self.subTest(target=target), self.assertRaises(WorkoutExerciseNotFoundError):
                    operation()
                self.assertEqual(self.writes, 0)
                self.assert_rolled_back(before)

    def test_out_of_range_positions_abort_without_changing_siblings(self) -> None:
        before = self.snapshot()
        operations = (
            lambda: self.service.create(
                USER_ID, WORKOUT_ID, WorkoutExerciseCreate(exercise_id=13, order_index=6)
            ),
            lambda: self.service.update(USER_ID, WORKOUT_ID, ENTRY_ID, WorkoutExerciseUpdate(order_index=5)),
        )
        for operation in operations:
            with self.assertRaises(WorkoutExerciseValidationError):
                operation()
            self.assertEqual(self.writes, 0)
            self.assert_rolled_back(before)

    def test_each_failed_write_rolls_back_inserts_moves_deletes_and_normalization(self) -> None:
        before = self.snapshot()
        for error, operation in (
            (
                WorkoutExerciseCreationError,
                lambda: self.service.create(
                    USER_ID, WORKOUT_ID, WorkoutExerciseCreate(exercise_id=13, order_index=0)
                ),
            ),
            (
                WorkoutExerciseUpdateError,
                lambda: self.service.update(
                    USER_ID, WORKOUT_ID, ENTRY_ID, WorkoutExerciseUpdate(order_index=4)
                ),
            ),
            (WorkoutExerciseDeleteError, lambda: self.service.delete(USER_ID, WORKOUT_ID, ENTRY_ID)),
        ):
            for step in (1, 2):
                self.fail_write = step
                with self.subTest(error=error, step=step), self.assertRaises(error):
                    operation()
                self.connections[-1].commit.assert_not_called()
                self.assert_rolled_back(before)

    def test_missing_and_invalid_readbacks_roll_back_insertion_and_both_move_directions(self) -> None:
        for missing in (True, False):
            self.missing_readback = missing
            self.invalid_readback = not missing
            for old, new in ((0, 4), (4, 0)):
                self.seed(5)
                before = self.snapshot()
                with self.assertRaises(WorkoutExerciseCreationError):
                    self.service.create(
                        USER_ID, WORKOUT_ID, WorkoutExerciseCreate(exercise_id=13, order_index=new)
                    )
                self.assert_rolled_back(before)
                error = WorkoutExerciseNotFoundError if missing else WorkoutExerciseUpdateError
                with self.assertRaises(error):
                    self.service.update(
                        USER_ID, WORKOUT_ID, ENTRY_ID + old, WorkoutExerciseUpdate(order_index=new)
                    )
                self.assert_rolled_back(before)

    def test_commit_failures_roll_back_all_three_mutations(self) -> None:
        self.fail_commit = True
        before = self.snapshot()
        for operation in (
            lambda: self.service.create(
                USER_ID, WORKOUT_ID, WorkoutExerciseCreate(exercise_id=13, order_index=0)
            ),
            lambda: self.service.update(USER_ID, WORKOUT_ID, ENTRY_ID, WorkoutExerciseUpdate(order_index=4)),
            lambda: self.service.delete(USER_ID, WORKOUT_ID, ENTRY_ID),
        ):
            with self.assertRaises(DatabaseError) as raised:
                operation()
            self.assertIs(raised.exception.__cause__, self.failure)
            self.connections[-1].commit.assert_called_once_with()
            self.assert_rolled_back(before)


class WorkoutExerciseRepositoryTests(TestCase):
    def setUp(self) -> None:
        self.executor = create_autospec(QueryExecutor, instance=True, spec_set=True)
        self.repo = WorkoutExerciseRepository(self.executor)
        self.executor.fetch_one.return_value = entry().model_dump()

    def test_missing_update_returns_none_before_shifting_or_writing(self) -> None:
        self.executor.fetch_one.return_value = None
        self.assertIsNone(self.repo.update(WORKOUT_ID, ENTRY_ID, WorkoutExerciseUpdate(order_index=2)))
        self.executor.execute_write.assert_not_called()

    def test_missing_readback_returns_none_so_the_service_can_abort_its_unit_of_work(self) -> None:
        self.executor.fetch_one.side_effect = [entry().model_dump(), None]
        self.assertIsNone(self.repo.update(WORKOUT_ID, ENTRY_ID, WorkoutExerciseUpdate(order_index=2)))
        self.assertEqual(self.executor.execute_write.call_count, 2)

    def test_statement_failures_keep_the_original_cause_without_owning_the_transaction(self) -> None:
        failure = OperationalError("injected write failure")
        self.executor.execute_write.side_effect = failure
        operations = (
            lambda: self.repo.create(WORKOUT_ID, WorkoutExerciseCreate(exercise_id=EXERCISE_ID, order_index=0)),
            lambda: self.repo.update(WORKOUT_ID, ENTRY_ID, WorkoutExerciseUpdate(notes="Changed")),
            lambda: self.repo.delete(WORKOUT_ID, ENTRY_ID),
        )
        for operation in operations:
            with self.assertRaises(WorkoutExerciseRepositoryError) as raised:
                operation()
            self.assertIs(raised.exception.__cause__, failure)


class UserUpdateReturnTests(TestCase):
    def test_missing_user_readback_returns_none_for_empty_null_and_real_changes(self) -> None:
        cases: tuple[dict[str, object], ...] = ({}, {"first_name": None}, {"first_name": "Updated"})
        for updates in cases:
            with (
                self.subTest(updates=updates),
                patch("repositories.user_repository.fetch_one", return_value=None),
                patch("repositories.user_repository.execute_write"),
            ):
                self.assertIsNone(UserRepository().update(USER_ID, **updates))
