"""Workout ownership, exercise visibility, and insertion/reordering boundaries."""

import unittest
from unittest.mock import call, create_autospec

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
from ports.repositories.exercise_repository import ExerciseRepositoryPort
from ports.repositories.workout_exercise_repository import WorkoutExerciseRepositoryPort
from ports.repositories.workout_repository import WorkoutRepositoryPort
from schemas.workout_exercises_schema import WorkoutExerciseCreate, WorkoutExerciseUpdate
from services.workout_exercise_service import WorkoutExerciseService
from tests.fixtures import ENTRY_ID, EXERCISE_ID, USER_ID, WORKOUT_ID, entry, exercise, workout


class WorkoutExerciseServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = create_autospec(WorkoutExerciseRepositoryPort, instance=True, spec_set=True)
        self.workouts = create_autospec(WorkoutRepositoryPort, instance=True, spec_set=True)
        self.exercises = create_autospec(ExerciseRepositoryPort, instance=True, spec_set=True)
        self.service = WorkoutExerciseService(self.repo, self.workouts, self.exercises)
        self.entry = entry()
        self.data = WorkoutExerciseCreate(exercise_id=EXERCISE_ID, order_index=0)
        self.updates = WorkoutExerciseUpdate(rest_seconds=0)
        self.workouts.get_by_user_and_id.return_value = workout()
        self.exercises.get_visible_by_id.return_value = exercise()
        self.repo.get_by_workout_and_id.return_value = self.entry
        self.repo.list_by_workout.return_value = [self.entry]
        self.repo.create.return_value = self.entry
        self.repo.update.return_value = self.entry
        self.repo.delete.return_value = True

    def test_missing_or_foreign_workout_blocks_all_entry_operations(self) -> None:
        operations = {
            "create": lambda: self.service.create_workout_exercise(USER_ID, WORKOUT_ID, self.data),
            "get": lambda: self.service.get_workout_exercise(USER_ID, WORKOUT_ID, ENTRY_ID),
            "list": lambda: self.service.list_workout_exercises(USER_ID, WORKOUT_ID),
            "update": lambda: self.service.update_workout_exercise(USER_ID, WORKOUT_ID, ENTRY_ID, self.updates),
            "delete": lambda: self.service.delete_workout_exercise(USER_ID, WORKOUT_ID, ENTRY_ID),
        }
        self.workouts.get_by_user_and_id.return_value = None
        for name, operation in operations.items():
            with self.subTest(operation=name):
                self.workouts.reset_mock()
                with self.assertRaises(WorkoutNotFoundError):
                    operation()
                self.workouts.get_by_user_and_id.assert_called_once_with(USER_ID, WORKOUT_ID)
                self.assertEqual(self.repo.mock_calls, [])
                self.assertEqual(self.exercises.mock_calls, [])

    def test_create_accepts_empty_workout_and_every_valid_insertion_position(self) -> None:
        for count in (0, 1, 3):
            for index in range(count + 1):
                with self.subTest(count=count, index=index):
                    self.repo.reset_mock()
                    self.exercises.reset_mock()
                    self.repo.list_by_workout.return_value = [
                        self.entry.model_copy(update={"id": ENTRY_ID + i, "order_index": i})
                        for i in range(count)
                    ]
                    data = WorkoutExerciseCreate(exercise_id=EXERCISE_ID, order_index=index)
                    self.assertIs(self.service.create_workout_exercise(USER_ID, WORKOUT_ID, data), self.entry)
                    self.exercises.get_visible_by_id.assert_called_once_with(EXERCISE_ID, USER_ID)
                    self.repo.list_by_workout.assert_called_once_with(WORKOUT_ID)
                    self.repo.create.assert_called_once_with(WORKOUT_ID, data)

    def test_create_rejects_index_beyond_end(self) -> None:
        for count in (0, 1, 3):
            with self.subTest(count=count):
                self.repo.list_by_workout.return_value = [self.entry] * count
                data = WorkoutExerciseCreate(exercise_id=EXERCISE_ID, order_index=count + 1)
                with self.assertRaises(WorkoutExerciseValidationError):
                    self.service.create_workout_exercise(USER_ID, WORKOUT_ID, data)
                self.repo.create.assert_not_called()

    def test_invisible_exercise_cannot_be_added(self) -> None:
        self.exercises.get_visible_by_id.return_value = None
        with self.assertRaises(ExerciseNotFoundError):
            self.service.create_workout_exercise(USER_ID, WORKOUT_ID, self.data)
        self.repo.list_by_workout.assert_not_called()
        self.repo.create.assert_not_called()

    def test_get_entry_checks_both_workout_and_entry_scope(self) -> None:
        self.assertIs(self.service.get_workout_exercise(USER_ID, WORKOUT_ID, ENTRY_ID), self.entry)
        self.workouts.get_by_user_and_id.assert_called_once_with(USER_ID, WORKOUT_ID)
        self.repo.get_by_workout_and_id.assert_called_once_with(WORKOUT_ID, ENTRY_ID)

    def test_list_returns_entries_or_empty_workout(self) -> None:
        for entries in ([self.entry], []):
            with self.subTest(entries=entries):
                self.repo.reset_mock()
                self.repo.list_by_workout.return_value = entries
                self.assertEqual(self.service.list_workout_exercises(USER_ID, WORKOUT_ID), entries)
                self.repo.list_by_workout.assert_called_once_with(WORKOUT_ID)

    def test_missing_or_wrong_workout_entry_blocks_read_update_and_delete(self) -> None:
        self.repo.get_by_workout_and_id.return_value = None
        operations = {
            "get": lambda: self.service.get_workout_exercise(USER_ID, WORKOUT_ID, ENTRY_ID),
            "update": lambda: self.service.update_workout_exercise(USER_ID, WORKOUT_ID, ENTRY_ID, self.updates),
            "delete": lambda: self.service.delete_workout_exercise(USER_ID, WORKOUT_ID, ENTRY_ID),
        }
        for name, operation in operations.items():
            with self.subTest(operation=name):
                self.repo.reset_mock()
                with self.assertRaises(WorkoutExerciseNotFoundError):
                    operation()
                self.assertEqual(self.repo.mock_calls, [call.get_by_workout_and_id(WORKOUT_ID, ENTRY_ID)])
                self.exercises.get_visible_by_id.assert_not_called()

    def test_update_accepts_each_existing_position(self) -> None:
        self.repo.list_by_workout.return_value = [self.entry] * 3
        for index in range(3):
            with self.subTest(index=index):
                self.repo.update.reset_mock()
                data = WorkoutExerciseUpdate(order_index=index)
                self.assertIs(
                    self.service.update_workout_exercise(USER_ID, WORKOUT_ID, ENTRY_ID, data),
                    self.entry,
                )
                self.repo.update.assert_called_once_with(WORKOUT_ID, ENTRY_ID, data)
                self.exercises.get_visible_by_id.assert_not_called()

    def test_update_cannot_move_to_append_position_or_reorder_empty_workout(self) -> None:
        for count in (0, 1, 3):
            with self.subTest(count=count):
                self.repo.list_by_workout.return_value = [self.entry] * count
                with self.assertRaises(WorkoutExerciseValidationError):
                    self.service.update_workout_exercise(
                        USER_ID,
                        WORKOUT_ID,
                        ENTRY_ID,
                        WorkoutExerciseUpdate(order_index=count),
                    )
                self.repo.update.assert_not_called()

    def test_update_rest_or_notes_does_not_require_exercise_replacement(self) -> None:
        for updates in (self.updates, WorkoutExerciseUpdate(notes="Slow tempo"), WorkoutExerciseUpdate()):
            with self.subTest(updates=updates):
                self.repo.update.reset_mock()
                self.service.update_workout_exercise(USER_ID, WORKOUT_ID, ENTRY_ID, updates)
                self.repo.update.assert_called_once_with(WORKOUT_ID, ENTRY_ID, updates)
                self.exercises.get_visible_by_id.assert_not_called()

    def test_replacement_exercise_must_be_visible(self) -> None:
        updates = WorkoutExerciseUpdate(exercise_id=29)
        self.service.update_workout_exercise(USER_ID, WORKOUT_ID, ENTRY_ID, updates)
        self.exercises.get_visible_by_id.assert_called_once_with(29, USER_ID)
        self.repo.update.assert_called_once_with(WORKOUT_ID, ENTRY_ID, updates)

    def test_invisible_replacement_prevents_update(self) -> None:
        self.exercises.get_visible_by_id.return_value = None
        with self.assertRaises(ExerciseNotFoundError):
            self.service.update_workout_exercise(
                USER_ID,
                WORKOUT_ID,
                ENTRY_ID,
                WorkoutExerciseUpdate(exercise_id=29),
            )
        self.repo.update.assert_not_called()

    def test_delete_owned_entry(self) -> None:
        self.service.delete_workout_exercise(USER_ID, WORKOUT_ID, ENTRY_ID)
        self.repo.delete.assert_called_once_with(WORKOUT_ID, ENTRY_ID)

    def test_entry_disappearing_during_write_raises_not_found(self) -> None:
        self.repo.update.return_value = None
        self.repo.delete.return_value = False
        with self.assertRaises(WorkoutExerciseNotFoundError):
            self.service.update_workout_exercise(USER_ID, WORKOUT_ID, ENTRY_ID, self.updates)
        with self.assertRaises(WorkoutExerciseNotFoundError):
            self.service.delete_workout_exercise(USER_ID, WORKOUT_ID, ENTRY_ID)

    def test_write_failures_raise_domain_errors_with_repository_cause(self) -> None:
        failure = WorkoutExerciseRepositoryError("database unavailable")
        self.repo.create.side_effect = failure
        self.repo.update.side_effect = failure
        self.repo.delete.side_effect = failure
        cases = (
            (
                WorkoutExerciseCreationError,
                lambda: self.service.create_workout_exercise(
                    USER_ID,
                    WORKOUT_ID,
                    self.data,
                ),
            ),
            (
                WorkoutExerciseUpdateError,
                lambda: self.service.update_workout_exercise(
                    USER_ID,
                    WORKOUT_ID,
                    ENTRY_ID,
                    self.updates,
                ),
            ),
            (
                WorkoutExerciseDeleteError,
                lambda: self.service.delete_workout_exercise(
                    USER_ID,
                    WORKOUT_ID,
                    ENTRY_ID,
                ),
            ),
        )
        for error, operation in cases:
            with (
                self.subTest(error=error.__name__),
                self.assertLogs("services.workout_exercise_service", level="ERROR"),
                self.assertRaises(error) as raised,
            ):
                operation()
            self.assertIs(raised.exception.__cause__, failure)
