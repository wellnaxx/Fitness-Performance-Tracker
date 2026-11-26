"""Readback and mapping must succeed before ordering changes commit."""

from __future__ import annotations

from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from core.errors.repository import WorkoutExerciseRepositoryError
from repositories.user_repository import UserRepository
from repositories.workout_exercise_repository import WorkoutExerciseRepository
from schemas.workout_exercises_schema import WorkoutExerciseCreate, WorkoutExerciseUpdate
from tests.fixtures import ENTRY_ID, EXERCISE_ID, USER_ID, WORKOUT_ID, entry


class WorkoutExerciseTransactionTests(TestCase):
    def setUp(self) -> None:
        self.repo = WorkoutExerciseRepository()
        self.connection = MagicMock()
        self.connection.__enter__.return_value = self.connection
        self.cursor = MagicMock()
        self.connection.cursor.return_value.__enter__.return_value = self.cursor
        self.enterContext(patch("data.executor.get_connection", return_value=self.connection))
        self.executor_log = self.enterContext(patch("data.executor.logger"))
        self.enterContext(patch.object(self.repo, "logger"))
        self.write = self.enterContext(
            patch("repositories.workout_exercise_repository.execute_write_tx", return_value=1)
        )
        self.insert = self.enterContext(
            patch("repositories.workout_exercise_repository.execute_insert_tx", return_value=ENTRY_ID)
        )
        self.row = entry().model_dump()
        self.fetch = self.enterContext(
            patch("repositories.workout_exercise_repository.fetch_one_tx", return_value=self.row)
        )
        self.data = WorkoutExerciseCreate(exercise_id=EXERCISE_ID, order_index=0)

    def test_create_validates_result_then_commits_once(self) -> None:
        result = self.repo.create(WORKOUT_ID, self.data)
        self.assertEqual(result, entry())
        self.connection.commit.assert_called_once_with()
        self.connection.rollback.assert_not_called()
        self.write.assert_called_once()
        self.insert.assert_called_once()

    def test_missing_insert_readback_rolls_back_instead_of_committing(self) -> None:
        self.fetch.return_value = None
        with self.assertRaises(WorkoutExerciseRepositoryError):
            self.repo.create(WORKOUT_ID, self.data)
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once_with()

    def test_invalid_insert_readback_rolls_back_mapping_and_schema_failures(self) -> None:
        for invalid in ({**self.row, "id": "invalid"}, {**self.row, "order_index": -1}):
            with self.subTest(row=invalid):
                self.connection.reset_mock()
                self.fetch.return_value = invalid
                with self.assertRaises(WorkoutExerciseRepositoryError):
                    self.repo.create(WORKOUT_ID, self.data)
                self.connection.commit.assert_not_called()
                self.connection.rollback.assert_called_once_with()

    def test_missing_update_returns_none_without_reordering(self) -> None:
        self.fetch.return_value = None
        self.assertIsNone(self.repo.update(WORKOUT_ID, ENTRY_ID, WorkoutExerciseUpdate(order_index=2)))
        self.write.assert_not_called()

    def test_empty_and_null_updates_return_current_values_without_writes(self) -> None:
        for updates in (WorkoutExerciseUpdate(), WorkoutExerciseUpdate(order_index=None, notes=None)):
            with self.subTest(updates=updates):
                self.assertEqual(self.repo.update(WORKOUT_ID, ENTRY_ID, updates), entry())
                self.write.assert_not_called()
                self.connection.rollback.assert_not_called()

    def test_disappearing_target_returns_none_and_rolls_back_both_reorder_directions(self) -> None:
        for old, new in ((0, 2), (2, 0)):
            with self.subTest(old=old, new=new):
                self.connection.reset_mock()
                self.write.reset_mock()
                self.fetch.side_effect = ({**self.row, "order_index": old}, None)
                self.assertIsNone(
                    self.repo.update(WORKOUT_ID, ENTRY_ID, WorkoutExerciseUpdate(order_index=new))
                )
                self.assertEqual(self.write.call_count, 2)
                self.connection.commit.assert_not_called()
                self.connection.rollback.assert_called_once_with()
                self.executor_log.exception.assert_not_called()

    def test_invalid_update_readback_rolls_back_all_changes(self) -> None:
        self.fetch.side_effect = (self.row, {**self.row, "id": "invalid"})
        with self.assertRaises(WorkoutExerciseRepositoryError):
            self.repo.update(WORKOUT_ID, ENTRY_ID, WorkoutExerciseUpdate(order_index=2))
        self.assertEqual(self.write.call_count, 2)
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once_with()

    def test_update_maps_result_before_commit(self) -> None:
        result_row = {**self.row, "order_index": 2}
        self.fetch.side_effect = (self.row, result_row)
        events = Mock()
        events.attach_mock(self.fetch, "fetch")
        events.attach_mock(self.connection.commit, "commit")
        result = self.repo.update(WORKOUT_ID, ENTRY_ID, WorkoutExerciseUpdate(order_index=2))
        self.assertIsNotNone(result)
        self.assertEqual([event[0] for event in events.mock_calls], ["fetch", "fetch", "commit"])
        self.connection.rollback.assert_not_called()

    def test_query_failure_rolls_back_and_keeps_the_original_cause(self) -> None:
        failure = RuntimeError("private query failure")
        self.write.side_effect = failure
        with self.assertRaises(WorkoutExerciseRepositoryError) as raised:
            self.repo.create(WORKOUT_ID, self.data)
        cause = raised.exception.__cause__
        if cause is None:
            self.fail("Expected the transaction error to preserve its cause")
        self.assertIs(cause.__cause__, failure)
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once_with()


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
