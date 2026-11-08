"""Bounded shifts execute the registered SQL against in-memory fixture rows.

SQLite exercises the portable UPDATE predicates with its placeholder syntax.
The cursor test separately checks the PostgreSQL transaction executor wiring.
"""

import sqlite3
from unittest import TestCase
from unittest.mock import MagicMock, create_autospec, patch

from data.executor import QueryExecutor
from data.queries import QUERIES
from repositories.set_entry_repository import SetEntryRepository
from repositories.set_entry_unit_of_work_repository import SetEntryUnitOfWorkRepository


class SetEntryRangeShiftTests(TestCase):
    def setUp(self) -> None:
        self.database = sqlite3.connect(":memory:")
        self.addCleanup(self.database.close)
        self.database.execute(
            "CREATE TABLE set_entries (id INTEGER PRIMARY KEY, workout_exercise_id INTEGER, set_number INTEGER)"
        )
        self.database.executemany(
            "INSERT INTO set_entries VALUES (?, ?, ?)",
            [(11, 17, 1), (12, 17, 2), (13, 17, 3), (14, 17, 4), (15, 17, 5), (21, 29, 3)],
        )
        executor = create_autospec(QueryExecutor, instance=True, spec_set=True)
        executor.execute_write.side_effect = self.execute_write
        self.repository = SetEntryRepository(executor)

    def execute_write(self, sql: str, params: tuple[object, ...] = ()) -> int:
        return self.database.execute(sql.replace("%s", "?"), params).rowcount

    def numbers(self) -> dict[int, int]:
        return dict(self.database.execute("SELECT id, set_number FROM set_entries"))

    def test_move_earlier_shifts_both_bounds_and_excludes_the_updated_target(self) -> None:
        self.database.execute("UPDATE set_entries SET set_number = 3 WHERE id = 15")
        self.repository.shift_set_numbers_in_range(17, start=3, end=4, delta=1, exclude_set_entry_id=15)
        self.assertEqual(self.numbers(), {11: 1, 12: 2, 13: 4, 14: 5, 15: 3, 21: 3})

    def test_move_later_shifts_both_bounds_and_excludes_the_updated_target(self) -> None:
        self.database.execute("UPDATE set_entries SET set_number = 5 WHERE id = 13")
        self.repository.shift_set_numbers_in_range(17, start=4, end=5, delta=-1, exclude_set_entry_id=13)
        self.assertEqual(self.numbers(), {11: 1, 12: 2, 13: 5, 14: 3, 15: 4, 21: 3})

    def test_single_position_range_changes_only_the_matching_entry(self) -> None:
        self.repository.shift_set_numbers_in_range(17, start=1, end=1, delta=1, exclude_set_entry_id=15)
        self.assertEqual(self.numbers(), {11: 2, 12: 2, 13: 3, 14: 4, 15: 5, 21: 3})

    def test_empty_reversed_excluded_and_zero_delta_ranges_leave_rows_unchanged(self) -> None:
        before = self.numbers()
        cases = (
            (17, 20, 30, 1, 15),
            (17, 4, 2, 1, 15),
            (99, 1, 5, 1, 15),
            (17, 5, 5, 1, 15),
            (17, 1, 5, 0, 15),
        )
        for parent, start, end, delta, excluded in cases:
            with self.subTest(parent=parent, start=start, end=end, delta=delta):
                self.repository.shift_set_numbers_in_range(parent, start, end, delta, excluded)
                self.assertEqual(self.numbers(), before)

    def test_unit_of_work_repository_uses_its_shared_cursor(self) -> None:
        cursor = MagicMock(spec_set=("execute", "rowcount"))
        cursor.rowcount = 2
        with patch("data.executor.get_connection", side_effect=AssertionError("Standalone connection used")):
            SetEntryUnitOfWorkRepository(cursor).shift_set_numbers_in_range(
                17, start=3, end=4, delta=1, exclude_set_entry_id=15
            )
        cursor.execute.assert_called_once_with(
            QUERIES.set_entries.shift_set_numbers_in_range, (1, 17, 3, 4, 15)
        )
