"""SQL asset loading and repository query assembly regression tests."""

from contextlib import chdir
from dataclasses import fields
from datetime import date
from functools import cached_property
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import create_autospec, patch

from core.errors.repository import UserRepositoryError
from data.executor import QueryExecutor
from data.loader import SQL_DIR, load_sql
from data.queries import QueryRegistry
from repositories.exercise_repository import ExerciseRepository
from repositories.meal_repository import MealRepository
from repositories.user_repository import UserRepository
from repositories.workout_exercise_repository import WorkoutExerciseRepository
from schemas.workout_exercises_schema import WorkoutExerciseCreate, WorkoutExerciseUpdate


def normalize(sql: str) -> str:
    return " ".join(sql.split())


class SqlLoadingTests(TestCase):
    def setUp(self) -> None:
        load_sql.cache_clear()
        self.addCleanup(load_sql.cache_clear)

    def test_loading_is_independent_of_working_directory(self) -> None:
        with TemporaryDirectory() as directory, chdir(directory):
            self.assertIn("FROM users", load_sql("users/get_by_id.sql"))

    def test_files_are_read_once_and_cached(self) -> None:
        with patch.object(Path, "read_text", return_value="  SELECT 1;\n") as read:
            self.assertEqual(load_sql("sample.sql"), "SELECT 1;")
            self.assertEqual(load_sql("sample.sql"), "SELECT 1;")
        read.assert_called_once_with(encoding="utf-8")

    def test_missing_file_raises_without_caching_failure(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_sql("missing/query.sql")
        self.assertEqual(load_sql.cache_info().currsize, 0)

    def test_registry_is_lazy_and_caches_query_groups(self) -> None:
        with patch("data.queries.load_sql", return_value="SELECT 1;") as read:
            registry = QueryRegistry()
            read.assert_not_called()
            users = registry.users
            count = read.call_count
            self.assertGreater(count, 0)
            self.assertIs(registry.users, users)
            self.assertEqual(read.call_count, count)
            self.assertTrue(all(call.args[0].startswith("users/") for call in read.call_args_list))

    def test_every_registered_asset_exists_and_every_sql_file_is_registered(self) -> None:
        registry = QueryRegistry()
        registered: set[str] = set()
        for group_name, member in vars(QueryRegistry).items():
            if not isinstance(member, cached_property):
                continue
            group = getattr(registry, group_name)
            for field in fields(group):
                relative_path = f"{group_name}/{field.name}.sql"
                with self.subTest(query=relative_path):
                    self.assertTrue(getattr(group, field.name))
                    self.assertEqual(getattr(group, field.name), load_sql(relative_path))
                registered.add(relative_path)
        self.assertEqual(registered, {path.relative_to(SQL_DIR).as_posix() for path in SQL_DIR.rglob("*.sql")})


class RepositoryQueryTests(TestCase):
    def test_exercise_filters_keep_values_bound_in_predicate_order(self) -> None:
        with patch("repositories.exercise_repository.fetch_all", return_value=[]) as fetch:
            ExerciseRepository().list_visible(
                user_id=7,
                search="50%_\\' OR TRUE --",
                muscle_group="chest",
                equipment="barbell",
                is_compound=False,
                is_custom=False,
                limit=5000,
                offset=-1,
            )
        sql, params = fetch.call_args.args
        self.assertIn("WHERE (created_by IS NULL OR created_by = %s)", sql)
        self.assertIn("AND is_compound = %s AND is_custom = %s", sql)
        self.assertNotIn("OR TRUE", sql)
        self.assertEqual(
            params,
            (
                7,
                "%50\\%\\_\\\\' OR TRUE --%",
                "%50\\%\\_\\\\' OR TRUE --%",
                "chest",
                "barbell",
                False,
                False,
                1000,
                0,
            ),
        )
        self.assertEqual(sql.count("%s"), len(params))

    def test_empty_exercise_filters_leave_a_complete_paginated_query(self) -> None:
        with patch("repositories.exercise_repository.fetch_all", return_value=[]) as fetch:
            ExerciseRepository().list_visible(7, limit=0)
        sql, params = fetch.call_args.args
        self.assertIn("WHERE (created_by IS NULL OR created_by = %s) ORDER BY", normalize(sql))
        self.assertNotIn("{", sql)
        self.assertEqual(params, (7, 1, 0))

    def test_meal_date_and_type_filters_preserve_parameter_order(self) -> None:
        start, end = date(2026, 1, 1), date(2026, 1, 31)
        with patch("repositories.meal_repository.fetch_all", return_value=[]) as fetch:
            MealRepository().list_by_user(7, date_from=start, date_to=end, meal_type="lunch")
        sql, params = fetch.call_args.args
        self.assertIn("AND eaten_at::date >= %s AND eaten_at::date <= %s AND meal_type = %s", sql)
        self.assertEqual(params, (7, start, end, "lunch", 100, 0))
        self.assertEqual(sql.count("%s"), len(params))

    def test_partial_update_interpolates_only_whitelisted_column_names(self) -> None:
        with (
            patch("repositories.user_repository.execute_write") as write,
            patch.object(UserRepository, "get_by_id", return_value=object()),
        ):
            UserRepository().update(7, first_name="O'Brien {test}", email=None)
        sql, params = write.call_args.args
        self.assertEqual(
            normalize(sql), "UPDATE users SET first_name = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s;"
        )
        self.assertEqual(params, ("O'Brien {test}", 7))

    def test_partial_update_rejects_unknown_columns_before_execution(self) -> None:
        with (
            patch("repositories.user_repository.execute_write") as write,
            self.assertRaises(UserRepositoryError),
        ):
            UserRepository().update(7, **{"id = 1; --": "bad"})
        write.assert_not_called()

    def test_workout_exercise_insert_uses_one_executor_for_shift_insert_and_read(self) -> None:
        executor = create_autospec(QueryExecutor, instance=True, spec_set=True)
        row: dict[str, object] = {
            "id": 17,
            "workout_id": 11,
            "exercise_id": 9,
            "order_index": 2,
            "rest_seconds": 60,
            "notes": None,
        }
        executor.execute_insert.return_value = 17
        executor.fetch_one.return_value = row
        result = WorkoutExerciseRepository(executor).create(
            11, WorkoutExerciseCreate(exercise_id=9, order_index=2, rest_seconds=60)
        )
        self.assertEqual(result.id, 17)
        self.assertIn("order_index = order_index + 1", executor.execute_write.call_args.args[0])
        self.assertEqual(executor.execute_write.call_args.args[1], (11, 2))
        self.assertEqual(executor.execute_insert.call_args.args[1], (11, 9, 2, 60, None))
        self.assertEqual(executor.fetch_one.call_args.args[1], (17,))

    def test_workout_exercise_reorder_preserves_both_shift_directions(self) -> None:
        for new_index, shift, expected_params in ((1, "+ 1", (11, 1, 3)), (5, "- 1", (11, 3, 5))):
            with self.subTest(new_index=new_index):
                executor = create_autospec(QueryExecutor, instance=True, spec_set=True)
                row: dict[str, object] = {
                    "id": 17,
                    "workout_id": 11,
                    "exercise_id": 9,
                    "order_index": 3,
                    "rest_seconds": 60,
                    "notes": None,
                }
                executor.fetch_one.side_effect = [row, {**row, "order_index": new_index}]
                result = WorkoutExerciseRepository(executor).update(
                    11, 17, WorkoutExerciseUpdate(order_index=new_index)
                )
                if result is None:
                    self.fail("Expected the reordered workout exercise to be returned")
                self.assertEqual(result.order_index, new_index)
                self.assertEqual(executor.execute_write.call_count, 2)
                first, second = executor.execute_write.call_args_list
                self.assertIn(f"order_index = order_index {shift}", first.args[0])
                self.assertEqual(first.args[1], expected_params)
                self.assertEqual(second.args[1], (new_index, 11, 17))

    def test_delete_normalizes_order_only_when_an_exercise_was_deleted(self) -> None:
        for deleted in (0, 1):
            with self.subTest(deleted=deleted):
                executor = create_autospec(QueryExecutor, instance=True, spec_set=True)
                executor.execute_write.return_value = deleted
                self.assertEqual(WorkoutExerciseRepository(executor).delete(11, 17), bool(deleted))
                self.assertEqual(executor.execute_write.call_count, 1 + deleted)
                self.assertEqual(executor.execute_write.call_args_list[0].args[1], (11, 17))
                if deleted:
                    self.assertIn("ROW_NUMBER()", executor.execute_write.call_args.args[0])
                    self.assertEqual(executor.execute_write.call_args.args[1], (11,))
