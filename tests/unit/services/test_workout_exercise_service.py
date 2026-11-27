"""Workout-exercise authorization, ordering, and explicit transaction boundaries."""

from collections.abc import Callable
from unittest import TestCase
from unittest.mock import Mock, call, create_autospec, patch

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
from dependencies.providers import get_workout_exercise_service
from ports.repositories.workout_exercise_repository import WorkoutExerciseRepositoryPort
from ports.repositories.workout_repository import WorkoutRepositoryPort
from ports.unit_of_work import UnitOfWorkPort, UnitOfWorkWorkoutExerciseRepositoryPort
from schemas.workout_exercises_schema import WorkoutExerciseCreate, WorkoutExerciseUpdate
from services.workout_exercise_service import WorkoutExerciseService
from tests.fixtures import ENTRY_ID, EXERCISE_ID, USER_ID, WORKOUT_ID, entry, workout


class WorkoutExerciseServiceTests(TestCase):
    def setUp(self) -> None:
        self.read_repo = create_autospec(WorkoutExerciseRepositoryPort, instance=True, spec_set=True)
        self.workouts = create_autospec(WorkoutRepositoryPort, instance=True, spec_set=True)
        self.repo = create_autospec(UnitOfWorkWorkoutExerciseRepositoryPort, instance=True, spec_set=True)
        self.uow = create_autospec(UnitOfWorkPort, instance=True, spec_set=True)
        self.uow.__enter__.return_value = self.uow
        self.uow.__exit__.return_value = None
        self.uow.workout_exercise = self.repo
        self.service = WorkoutExerciseService(self.read_repo, self.workouts, self.uow)
        self.entry = entry()
        self.data = WorkoutExerciseCreate(exercise_id=EXERCISE_ID, order_index=0)
        self.updates = WorkoutExerciseUpdate(rest_seconds=0)
        self.workouts.get_by_user_and_id.return_value = workout()
        self.repo.lock_for_workout.return_value = True
        self.repo.lock_visible_exercise.return_value = True
        for repository in (self.read_repo, self.repo):
            repository.get_by_workout_and_id.return_value = self.entry
            repository.list_by_workout.return_value = [self.entry]
        self.repo.create.return_value = self.entry
        self.repo.update.return_value = self.entry
        self.repo.delete.return_value = True
        self.logger = self.enterContext(patch.object(self.service, "logger"))

    def mutations(self) -> tuple[Callable[[], object], ...]:
        return (
            lambda: self.service.create(USER_ID, WORKOUT_ID, self.data),
            lambda: self.service.update(USER_ID, WORKOUT_ID, ENTRY_ID, self.updates),
            lambda: self.service.delete(USER_ID, WORKOUT_ID, ENTRY_ID),
        )

    def test_provider_passes_the_transaction_boundary_without_entering_it(self) -> None:
        service = get_workout_exercise_service(self.read_repo, self.workouts, self.uow)
        self.assertIs(service.unit_of_work, self.uow)
        self.assertIs(service.workout_exercise_repository, self.read_repo)
        self.uow.__enter__.assert_not_called()

    def test_unavailable_parent_blocks_writes_before_child_lookups(self) -> None:
        self.repo.lock_for_workout.return_value = False
        for operation in self.mutations():
            with self.subTest(operation=operation):
                self.repo.reset_mock()
                self.uow.reset_mock()
                with self.assertRaises(WorkoutNotFoundError):
                    operation()
                self.assertEqual(self.repo.mock_calls, [call.lock_for_workout(USER_ID, WORKOUT_ID)])
                self.uow.commit.assert_not_called()
                self.uow.__exit__.assert_called_once()
                self.assertEqual(self.read_repo.mock_calls, [])
                self.assertEqual(self.workouts.mock_calls, [])

    def test_create_accepts_empty_workout_and_every_valid_insertion_position(self) -> None:
        for count in (0, 1, 3):
            for index in range(count + 1):
                with self.subTest(count=count, index=index):
                    self.repo.reset_mock()
                    self.uow.reset_mock()
                    self.repo.list_by_workout.return_value = [self.entry] * count
                    data = WorkoutExerciseCreate(exercise_id=EXERCISE_ID, order_index=index)
                    self.assertIs(self.service.create(USER_ID, WORKOUT_ID, data), self.entry)
                    self.assertEqual(
                        self.repo.mock_calls,
                        [
                            call.lock_for_workout(USER_ID, WORKOUT_ID),
                            call.lock_visible_exercise(USER_ID, EXERCISE_ID),
                            call.list_by_workout(WORKOUT_ID),
                            call.create(WORKOUT_ID, data),
                        ],
                    )
                    self.uow.commit.assert_called_once_with()
                    self.assertEqual(self.read_repo.mock_calls, [])
                    self.assertEqual(self.workouts.mock_calls, [])

    def test_create_rejects_positions_outside_the_insertion_range(self) -> None:
        for count in (0, 1, 3):
            for index in (-1, count + 1):
                with self.subTest(count=count, index=index):
                    self.repo.list_by_workout.return_value = [self.entry] * count
                    data = self.data.model_copy(update={"order_index": index})
                    with self.assertRaises(WorkoutExerciseValidationError):
                        self.service.create(USER_ID, WORKOUT_ID, data)
                    self.repo.create.assert_not_called()
                    self.uow.commit.assert_not_called()
                    self.logger.info.assert_not_called()

    def test_invisible_or_missing_exercise_blocks_create_before_counting(self) -> None:
        self.repo.lock_visible_exercise.return_value = False
        with self.assertRaises(ExerciseNotFoundError):
            self.service.create(USER_ID, WORKOUT_ID, self.data)
        self.repo.list_by_workout.assert_not_called()
        self.repo.create.assert_not_called()
        self.uow.commit.assert_not_called()

    def test_reads_use_scoped_repositories_without_opening_a_transaction(self) -> None:
        self.assertIs(self.service.get_by_id(USER_ID, WORKOUT_ID, ENTRY_ID), self.entry)
        self.read_repo.get_by_workout_and_id.assert_called_once_with(WORKOUT_ID, ENTRY_ID)
        for entries in ([self.entry], []):
            self.read_repo.list_by_workout.return_value = entries
            self.assertEqual(self.service.list_by_workout(USER_ID, WORKOUT_ID), entries)
        self.assertEqual(self.workouts.get_by_user_and_id.call_count, 3)
        self.uow.__enter__.assert_not_called()
        self.assertEqual(self.repo.mock_calls, [])

    def test_missing_parent_blocks_reads_before_child_lookups(self) -> None:
        self.workouts.get_by_user_and_id.return_value = None
        for operation in (
            lambda: self.service.get_by_id(USER_ID, WORKOUT_ID, ENTRY_ID),
            lambda: self.service.list_by_workout(USER_ID, WORKOUT_ID),
        ):
            with self.assertRaises(WorkoutNotFoundError):
                operation()
        self.assertEqual(self.read_repo.mock_calls, [])
        self.uow.__enter__.assert_not_called()

    def test_missing_or_wrong_parent_child_blocks_read_update_and_delete(self) -> None:
        self.read_repo.get_by_workout_and_id.return_value = None
        self.repo.get_by_workout_and_id.return_value = None
        with self.assertRaises(WorkoutExerciseNotFoundError):
            self.service.get_by_id(USER_ID, WORKOUT_ID, ENTRY_ID)
        for operation in self.mutations()[1:]:
            self.repo.reset_mock()
            with self.assertRaises(WorkoutExerciseNotFoundError):
                operation()
            self.assertEqual(
                self.repo.mock_calls,
                [
                    call.lock_for_workout(USER_ID, WORKOUT_ID),
                    call.get_by_workout_and_id(WORKOUT_ID, ENTRY_ID),
                ],
            )
            self.uow.commit.assert_not_called()

    def test_update_accepts_each_existing_position_after_the_parent_lock(self) -> None:
        self.repo.list_by_workout.return_value = [self.entry] * 3
        for index in range(3):
            with self.subTest(index=index):
                self.repo.reset_mock()
                self.uow.reset_mock()
                updates = WorkoutExerciseUpdate(order_index=index)
                self.assertIs(self.service.update(USER_ID, WORKOUT_ID, ENTRY_ID, updates), self.entry)
                self.assertEqual(
                    self.repo.mock_calls,
                    [
                        call.lock_for_workout(USER_ID, WORKOUT_ID),
                        call.get_by_workout_and_id(WORKOUT_ID, ENTRY_ID),
                        call.list_by_workout(WORKOUT_ID),
                        call.update(WORKOUT_ID, ENTRY_ID, updates),
                    ],
                )
                self.uow.commit.assert_called_once_with()

    def test_update_rejects_negative_append_and_empty_workout_positions(self) -> None:
        for count in (0, 1, 3):
            for index in (-1, count):
                with self.subTest(count=count, index=index):
                    self.repo.list_by_workout.return_value = [self.entry] * count
                    updates = self.updates.model_copy(update={"order_index": index})
                    with self.assertRaises(WorkoutExerciseValidationError):
                        self.service.update(USER_ID, WORKOUT_ID, ENTRY_ID, updates)
                    self.repo.update.assert_not_called()
                    self.uow.commit.assert_not_called()

    def test_nonposition_updates_skip_siblings_and_lock_references_only_when_needed(self) -> None:
        for updates in (
            WorkoutExerciseUpdate(),
            WorkoutExerciseUpdate(order_index=None, notes=None),
            self.updates,
            WorkoutExerciseUpdate(notes="Changed"),
            WorkoutExerciseUpdate(exercise_id=EXERCISE_ID),
        ):
            with self.subTest(updates=updates):
                self.repo.reset_mock()
                self.service.update(USER_ID, WORKOUT_ID, ENTRY_ID, updates)
                self.repo.list_by_workout.assert_not_called()
                self.repo.update.assert_called_once_with(WORKOUT_ID, ENTRY_ID, updates)
                if updates.exercise_id is None:
                    self.repo.lock_visible_exercise.assert_not_called()
                else:
                    self.repo.lock_visible_exercise.assert_called_once_with(USER_ID, EXERCISE_ID)

    def test_invisible_replacement_prevents_counting_and_writes(self) -> None:
        self.repo.lock_visible_exercise.return_value = False
        with self.assertRaises(ExerciseNotFoundError):
            self.service.update(
                USER_ID, WORKOUT_ID, ENTRY_ID, WorkoutExerciseUpdate(exercise_id=29, order_index=0)
            )
        self.repo.list_by_workout.assert_not_called()
        self.repo.update.assert_not_called()
        self.uow.commit.assert_not_called()

    def test_delete_uses_only_locked_transaction_repository(self) -> None:
        self.service.delete(USER_ID, WORKOUT_ID, ENTRY_ID)
        self.assertEqual(
            self.repo.mock_calls,
            [
                call.lock_for_workout(USER_ID, WORKOUT_ID),
                call.get_by_workout_and_id(WORKOUT_ID, ENTRY_ID),
                call.delete(WORKOUT_ID, ENTRY_ID),
            ],
        )
        self.uow.commit.assert_called_once_with()
        self.assertEqual(self.read_repo.mock_calls, [])
        self.assertEqual(self.workouts.mock_calls, [])

    def test_missing_readback_and_failed_delete_exit_with_error_before_commit(self) -> None:
        self.repo.update.return_value = None
        self.repo.delete.return_value = False
        for operation in self.mutations()[1:]:
            self.uow.reset_mock()
            with self.assertRaises(WorkoutExerciseNotFoundError):
                operation()
            self.uow.commit.assert_not_called()
            self.assertIs(self.uow.__exit__.call_args.args[0], WorkoutExerciseNotFoundError)
            self.logger.info.assert_not_called()

    def test_repository_write_errors_are_translated_after_transaction_exit(self) -> None:
        failure = WorkoutExerciseRepositoryError("private query details")
        for name in ("create", "update", "delete"):
            getattr(self.repo, name).side_effect = failure
        errors = (WorkoutExerciseCreationError, WorkoutExerciseUpdateError, WorkoutExerciseDeleteError)
        for error, operation in zip(errors, self.mutations(), strict=True):
            with self.subTest(error=error), self.assertRaises(error) as raised:
                operation()
            self.assertIs(raised.exception.__cause__, failure)
            self.assertIs(self.uow.__exit__.call_args.args[1], failure)
            self.uow.commit.assert_not_called()
            self.logger.info.assert_not_called()

    def test_lock_and_count_errors_abort_before_writes(self) -> None:
        for name in ("lock_for_workout", "lock_visible_exercise", "list_by_workout"):
            failure = DatabaseError("injected read failure")
            with patch.object(self.repo, name, side_effect=failure), self.assertRaises(DatabaseError) as raised:
                self.service.create(USER_ID, WORKOUT_ID, self.data)
            self.assertIs(raised.exception, failure)
            self.repo.create.assert_not_called()
            self.uow.commit.assert_not_called()
            self.logger.info.assert_not_called()

    def test_success_is_logged_only_after_commit_and_transaction_exit(self) -> None:
        for operation in self.mutations():
            self.uow.reset_mock()
            self.logger.reset_mock()
            events = Mock()
            events.attach_mock(self.uow.__enter__, "enter")
            events.attach_mock(self.uow.commit, "commit")
            events.attach_mock(self.uow.__exit__, "exit")
            events.attach_mock(self.logger.info, "success")
            operation()
            self.assertEqual([event[0] for event in events.mock_calls], ["enter", "commit", "exit", "success"])

    def test_enter_commit_and_exit_errors_propagate_without_success_logging(self) -> None:
        for step in ("__enter__", "commit", "__exit__"):
            for operation in self.mutations():
                failure = DatabaseError("injected transaction failure")
                with (
                    self.subTest(step=step, operation=operation),
                    patch.object(self.uow, step, side_effect=failure),
                    self.assertRaises(DatabaseError) as raised,
                ):
                    operation()
                self.assertIs(raised.exception, failure)
                self.logger.info.assert_not_called()
