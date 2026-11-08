"""Owned set CRUD, one-based ordering boundaries, and transaction failure paths."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import TestCase
from unittest.mock import call, create_autospec, patch

from core.errors.database import DatabaseError
from core.errors.repository import SetEntryRepositoryError
from core.errors.set_entry import (
    SetEntryCreationError,
    SetEntryDeleteError,
    SetEntryNotFoundError,
    SetEntryValidationError,
)
from core.errors.workout import WorkoutNotFoundError
from core.errors.workout_exercise import WorkoutExerciseNotFoundError, WorkoutExerciseValidationError
from ports.repositories.set_entry_repository import SetEntryRepositoryPort
from ports.repositories.workout_exercise_repository import WorkoutExerciseRepositoryPort
from ports.repositories.workout_repository import WorkoutRepositoryPort
from ports.unit_of_work import UnitOfWorkPort, UnitOfWorkSetEntryRepositoryPort
from schemas.set_entry_schema import SetEntryCreate, SetEntryUpdate
from services.set_entry_service import SetEntryService
from tests.fixtures import ENTRY_ID, SET_ENTRY_ID, USER_ID, WORKOUT_ID, entry, set_entry, workout

if TYPE_CHECKING:
    from collections.abc import Callable

    from schemas.set_entry_schema import SetEntryPublic


class SetEntryServiceTests(TestCase):
    def setUp(self) -> None:
        self.sets = create_autospec(SetEntryRepositoryPort, instance=True, spec_set=True)
        self.exercises = create_autospec(WorkoutExerciseRepositoryPort, instance=True, spec_set=True)
        self.workouts = create_autospec(WorkoutRepositoryPort, instance=True, spec_set=True)
        self.tx = create_autospec(UnitOfWorkSetEntryRepositoryPort, instance=True, spec_set=True)
        self.uow = create_autospec(UnitOfWorkPort, instance=True, spec_set=True)
        self.uow.set_entry = self.tx
        self.uow.__enter__.return_value = self.uow
        self.uow.__exit__.return_value = None
        self.service = SetEntryService(self.sets, self.exercises, self.workouts, self.uow)
        self.record = set_entry()
        self.data = SetEntryCreate.model_validate(self.record.model_dump())
        self.sets.get_by_id.return_value = self.record
        self.sets.list_by_workout_exercise.return_value = [self.record]
        self.exercises.get_by_id.return_value = entry()
        self.workouts.get_by_user_and_id.return_value = workout()
        self.tx.lock_for_workout_exercise.return_value = True
        self.tx.get_by_workout_exercise_and_id.return_value = self.record
        self.tx.list_by_workout_exercise.return_value = [self.record] * 5
        self.tx.create.return_value = self.record
        self.tx.update_in_workout_exercise.return_value = self.record
        self.tx.delete_in_workout_exercise.return_value = True
        # Every mutation must go through the transaction-bound repository.
        for method in (
            "create",
            "update_in_workout_exercise",
            "delete_in_workout_exercise",
            "shift_set_numbers",
            "shift_set_numbers_in_range",
            "normalize_set_numbers",
        ):
            getattr(self.sets, method).side_effect = AssertionError("Write outside unit of work")

    def operations(self) -> dict[str, Callable[[], object]]:
        return {
            "create": lambda: self.service.create(USER_ID, self.data),
            "get": lambda: self.service.get_by_id(USER_ID, SET_ENTRY_ID),
            "list": lambda: self.service.list_by_workout_exercise(USER_ID, ENTRY_ID),
            "update": lambda: self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate(reps=0)),
            "delete": lambda: self.service.delete(USER_ID, ENTRY_ID, SET_ENTRY_ID),
        }

    def test_get_returns_the_set_after_checking_its_ownership_chain(self) -> None:
        self.assertIs(self.service.get_by_id(USER_ID, SET_ENTRY_ID), self.record)
        self.sets.get_by_id.assert_called_once_with(SET_ENTRY_ID)
        self.exercises.get_by_id.assert_called_once_with(ENTRY_ID)
        self.workouts.get_by_user_and_id.assert_called_once_with(USER_ID, WORKOUT_ID)
        self.uow.__enter__.assert_not_called()

    def test_list_returns_sets_or_empty_list_without_a_write_transaction(self) -> None:
        pages: tuple[list[SetEntryPublic], ...] = ([self.record], [])
        for records in pages:
            with self.subTest(records=records):
                self.sets.list_by_workout_exercise.reset_mock()
                self.sets.list_by_workout_exercise.return_value = records
                self.assertEqual(self.service.list_by_workout_exercise(USER_ID, ENTRY_ID), records)
                self.sets.list_by_workout_exercise.assert_called_once_with(ENTRY_ID)
        self.uow.__enter__.assert_not_called()

    def test_missing_set_blocks_get_update_and_delete_before_parent_lookups(self) -> None:
        self.sets.get_by_id.return_value = None
        for name in ("get", "update", "delete"):
            with self.subTest(operation=name), self.assertRaises(SetEntryNotFoundError):
                self.operations()[name]()
        self.exercises.get_by_id.assert_not_called()
        self.workouts.get_by_user_and_id.assert_not_called()
        self.uow.__enter__.assert_not_called()

    def test_missing_workout_exercise_blocks_every_operation(self) -> None:
        self.exercises.get_by_id.return_value = None
        for name, operation in self.operations().items():
            with self.subTest(operation=name), self.assertRaises(WorkoutExerciseNotFoundError):
                operation()
        self.workouts.get_by_user_and_id.assert_not_called()
        self.uow.__enter__.assert_not_called()
        self.assertEqual(self.tx.mock_calls, [])

    def test_missing_or_foreign_workout_blocks_every_operation(self) -> None:
        self.workouts.get_by_user_and_id.return_value = None
        for name, operation in self.operations().items():
            with (
                self.subTest(operation=name),
                self.assertLogs("services.ownership", level="WARNING"),
                self.assertRaises(WorkoutNotFoundError),
            ):
                operation()
        self.uow.__enter__.assert_not_called()
        self.assertEqual(self.tx.mock_calls, [])

    def test_parent_mismatch_is_rejected_after_authorization(self) -> None:
        operations = (
            lambda: self.service.update(USER_ID, 99, SET_ENTRY_ID, SetEntryUpdate(reps=8)),
            lambda: self.service.delete(USER_ID, 99, SET_ENTRY_ID),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                self.workouts.reset_mock()
                with self.assertRaises(WorkoutExerciseValidationError):
                    operation()
                self.workouts.get_by_user_and_id.assert_called_once_with(USER_ID, WORKOUT_ID)
        self.uow.__enter__.assert_not_called()

    def test_foreign_caller_cannot_obtain_parent_id_through_mismatch_errors(self) -> None:
        self.workouts.get_by_user_and_id.return_value = None
        operations = (
            lambda: self.service.update(USER_ID + 1, 99, SET_ENTRY_ID, SetEntryUpdate()),
            lambda: self.service.delete(USER_ID + 1, 99, SET_ENTRY_ID),
        )
        for operation in operations:
            with (
                self.subTest(operation=operation),
                self.assertLogs("services.ownership", level="WARNING"),
                self.assertRaises(WorkoutNotFoundError),
            ):
                operation()
        self.uow.__enter__.assert_not_called()

    def test_parent_disappearing_before_lock_blocks_all_writes(self) -> None:
        self.tx.lock_for_workout_exercise.return_value = False
        for name in ("create", "update", "delete"):
            with self.subTest(operation=name):
                self.tx.reset_mock()
                with self.assertRaises(WorkoutExerciseNotFoundError):
                    self.operations()[name]()
                self.assertEqual(self.tx.mock_calls, [call.lock_for_workout_exercise(ENTRY_ID)])
        self.uow.commit.assert_not_called()

    def test_create_accepts_every_position_and_shifts_only_for_insertion(self) -> None:
        for count in (0, 1, 3, 5):
            for position in range(1, count + 2):
                with self.subTest(count=count, position=position):
                    self.tx.reset_mock()
                    self.uow.reset_mock()
                    self.tx.list_by_workout_exercise.return_value = [self.record] * count
                    data = self.data.model_copy(update={"set_number": position})
                    self.assertIs(self.service.create(USER_ID, data), self.record)
                    expected = [
                        call.lock_for_workout_exercise(ENTRY_ID),
                        call.list_by_workout_exercise(ENTRY_ID),
                    ]
                    if position <= count:
                        expected.append(call.shift_set_numbers(ENTRY_ID, position, delta=1))
                    expected.append(call.create(data))
                    self.assertEqual(self.tx.mock_calls, expected)
                    self.uow.commit.assert_called_once_with()
                    self.uow.__exit__.assert_called_once_with(None, None, None)

    def test_create_rejects_positions_beyond_the_append_position(self) -> None:
        for count in (0, 1, 5):
            with self.subTest(count=count):
                self.tx.list_by_workout_exercise.return_value = [self.record] * count
                with self.assertRaises(SetEntryValidationError):
                    self.service.create(USER_ID, self.data.model_copy(update={"set_number": count + 2}))
        self.tx.shift_set_numbers.assert_not_called()
        self.tx.create.assert_not_called()
        self.uow.commit.assert_not_called()

    def test_create_wraps_repository_error_and_preserves_its_cause(self) -> None:
        failure = SetEntryRepositoryError("private insert details")
        self.tx.create.side_effect = failure
        with self.assertRaises(SetEntryCreationError) as raised:
            self.service.create(USER_ID, self.data)
        self.assertIs(raised.exception.__cause__, failure)
        self.assertNotIn("private", str(raised.exception))
        self.uow.commit.assert_not_called()
        self.assertIs(self.uow.__exit__.call_args.args[1], raised.exception)

    def test_update_moves_between_every_pair_of_existing_positions(self) -> None:
        for count in (2, 3, 5):
            for old in range(1, count + 1):
                for new in range(1, count + 1):
                    if old == new:
                        continue
                    with self.subTest(count=count, old=old, new=new):
                        self.tx.reset_mock()
                        self.uow.reset_mock()
                        self.tx.get_by_workout_exercise_and_id.return_value = self.record.model_copy(
                            update={"set_number": old}
                        )
                        self.tx.list_by_workout_exercise.return_value = [self.record] * count
                        updates = SetEntryUpdate(set_number=new)
                        self.assertIs(
                            self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, updates), self.record
                        )
                        self.tx.shift_set_numbers_in_range.assert_called_once_with(
                            ENTRY_ID,
                            start=new if new < old else old + 1,
                            end=old - 1 if new < old else new,
                            delta=1 if new < old else -1,
                            exclude_set_entry_id=SET_ENTRY_ID,
                        )
                        self.tx.update_in_workout_exercise.assert_called_once_with(
                            ENTRY_ID, SET_ENTRY_ID, updates
                        )
                        self.tx.shift_set_numbers.assert_not_called()
                        self.uow.commit.assert_called_once_with()

    def test_update_uses_position_read_under_lock_instead_of_the_earlier_copy(self) -> None:
        self.tx.get_by_workout_exercise_and_id.return_value = self.record.model_copy(update={"set_number": 5})
        self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate(set_number=2))
        self.tx.shift_set_numbers_in_range.assert_called_once_with(
            ENTRY_ID, start=2, end=4, delta=1, exclude_set_entry_id=SET_ENTRY_ID
        )

    def test_update_without_position_delegates_empty_nullable_zero_and_false_changes(self) -> None:
        for updates in (
            SetEntryUpdate(),
            SetEntryUpdate(rpe=None),
            SetEntryUpdate(reps=0, weight=0, is_warmup=False, completed=False),
        ):
            with self.subTest(updates=updates):
                self.tx.reset_mock()
                self.uow.reset_mock()
                self.assertIs(self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, updates), self.record)
                self.tx.update_in_workout_exercise.assert_called_once_with(ENTRY_ID, SET_ENTRY_ID, updates)
                self.tx.list_by_workout_exercise.assert_not_called()
                self.tx.shift_set_numbers_in_range.assert_not_called()
                self.uow.commit.assert_called_once_with()

    def test_explicit_unchanged_position_is_rejected_even_with_other_changes(self) -> None:
        for updates in (SetEntryUpdate(set_number=3), SetEntryUpdate(set_number=3, reps=8)):
            with self.subTest(updates=updates), self.assertRaises(SetEntryValidationError):
                self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, updates)
        self.tx.update_in_workout_exercise.assert_not_called()
        self.tx.shift_set_numbers_in_range.assert_not_called()
        self.uow.commit.assert_not_called()

    def test_update_rejects_append_position_or_an_empty_parent(self) -> None:
        for count, position in ((5, 6), (1, 2), (0, 1)):
            with self.subTest(count=count, position=position):
                self.tx.list_by_workout_exercise.return_value = [self.record] * count
                with self.assertRaises(SetEntryValidationError):
                    self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate(set_number=position))
        self.tx.shift_set_numbers_in_range.assert_not_called()
        self.tx.update_in_workout_exercise.assert_not_called()
        self.uow.commit.assert_not_called()

    def test_set_disappearing_before_locked_read_blocks_update_and_delete(self) -> None:
        self.tx.get_by_workout_exercise_and_id.return_value = None
        for name in ("update", "delete"):
            with self.subTest(operation=name), self.assertRaises(SetEntryNotFoundError):
                self.operations()[name]()
        self.tx.update_in_workout_exercise.assert_not_called()
        self.tx.delete_in_workout_exercise.assert_not_called()
        self.tx.normalize_set_numbers.assert_not_called()
        self.uow.commit.assert_not_called()

    def test_missing_update_readback_does_not_commit_prior_shifts(self) -> None:
        self.tx.update_in_workout_exercise.return_value = None
        with self.assertRaises(SetEntryNotFoundError):
            self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate(set_number=5))
        self.tx.shift_set_numbers_in_range.assert_called_once()
        self.uow.commit.assert_not_called()

    def test_delete_normalizes_after_deletion_and_commits(self) -> None:
        self.assertIsNone(self.service.delete(USER_ID, ENTRY_ID, SET_ENTRY_ID))
        self.assertEqual(
            self.tx.mock_calls,
            [
                call.lock_for_workout_exercise(ENTRY_ID),
                call.get_by_workout_exercise_and_id(ENTRY_ID, SET_ENTRY_ID),
                call.delete_in_workout_exercise(ENTRY_ID, SET_ENTRY_ID),
                call.normalize_set_numbers(ENTRY_ID),
            ],
        )
        self.uow.commit.assert_called_once_with()

    def test_delete_returning_false_raises_without_normalization_or_commit(self) -> None:
        self.tx.delete_in_workout_exercise.return_value = False
        with self.assertRaises(SetEntryDeleteError):
            self.service.delete(USER_ID, ENTRY_ID, SET_ENTRY_ID)
        self.tx.normalize_set_numbers.assert_not_called()
        self.uow.commit.assert_not_called()

    def test_failures_at_each_write_step_leave_the_context_without_committing(self) -> None:
        cases: tuple[tuple[str, Callable[[], object]], ...] = (
            ("shift_set_numbers", self.operations()["create"]),
            ("create", self.operations()["create"]),
            (
                "shift_set_numbers_in_range",
                lambda: self.service.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate(set_number=5)),
            ),
            ("update_in_workout_exercise", self.operations()["update"]),
            ("delete_in_workout_exercise", self.operations()["delete"]),
            ("normalize_set_numbers", self.operations()["delete"]),
        )
        for method, operation in cases:
            with self.subTest(method=method):
                self.uow.reset_mock()
                failure = DatabaseError("write failed")
                with (
                    patch.object(self.tx, method, side_effect=failure),
                    self.assertRaises(DatabaseError) as raised,
                ):
                    operation()
                self.assertIs(raised.exception, failure)
                self.assertIs(self.uow.__exit__.call_args.args[1], failure)
                self.uow.commit.assert_not_called()

    def test_repository_read_error_propagates_without_becoming_not_found(self) -> None:
        failure = SetEntryRepositoryError("read failed")
        self.sets.get_by_id.side_effect = failure
        with self.assertRaises(SetEntryRepositoryError) as raised:
            self.service.get_by_id(USER_ID, SET_ENTRY_ID)
        self.assertIs(raised.exception, failure)
        self.workouts.get_by_user_and_id.assert_not_called()
