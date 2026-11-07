"""Owned set-entry CRUD with atomic insertion, reordering, and deletion."""

from collections.abc import Generator
from contextlib import contextmanager

from core.errors.repository import SetEntryRepositoryError
from core.errors.set_entry import (
    SetEntryCreationError,
    SetEntryDeleteError,
    SetEntryNotFoundError,
    SetEntryValidationError,
)
from core.errors.workout_exercise import WorkoutExerciseNotFoundError, WorkoutExerciseValidationError
from ports.repositories.set_entry_repository import SetEntryRepositoryPort
from ports.repositories.workout_exercise_repository import WorkoutExerciseRepositoryPort
from ports.repositories.workout_repository import WorkoutRepositoryPort
from ports.unit_of_work import UnitOfWorkPort
from schemas.set_entry_schema import SetEntryCreate, SetEntryPublic, SetEntryUpdate
from services.ownership import require_owned_workout


class SetEntryService:
    """Enforce the set -> workout exercise -> owned workout access chain.

    Set numbers are consecutive and start at 1. Mutations lock the parent
    workout exercise and use transaction-bound repositories for all set reads
    and writes. Commit only after persistence and result mapping succeed.

    Ownership is verified before locking or reporting mismatched parent IDs.
    An explicitly unchanged position is rejected; omit set_number to update
    other fields while keeping the current position.
    """

    def __init__(
        self,
        set_entry_repo: SetEntryRepositoryPort,
        workout_exercise_repo: WorkoutExerciseRepositoryPort,
        workout_repo: WorkoutRepositoryPort,
        unit_of_work: UnitOfWorkPort,
    ) -> None:
        """Inject read repositories and an explicit transaction boundary for writes."""
        self.set_entry_repo = set_entry_repo
        self.workout_exercise_repo = workout_exercise_repo
        self.workout_repo = workout_repo
        self.unit_of_work = unit_of_work

    @contextmanager
    def _set_entry_transaction(self, workout_exercise_id: int) -> Generator[UnitOfWorkPort]:
        """Lock the parent before reading positions; roll back unless the caller commits.

        Raises:
            WorkoutExerciseNotFoundError: If the parent disappeared before locking.
            DatabaseError: If opening, locking, committing, or rolling back fails.
        """
        with self.unit_of_work as uow:
            if not uow.set_entry.lock_for_workout_exercise(workout_exercise_id):
                raise WorkoutExerciseNotFoundError.not_found(workout_exercise_id)
            yield uow

    def create(self, user_id: int, set_entry_data: SetEntryCreate) -> SetEntryPublic:
        """Insert into an owned exercise at a position from 1 through count + 1.

        Args:
            user_id: Authenticated user ID.
            set_entry_data: Validated payload containing the parent exercise ID.

        Returns:
            The persisted set, after shifting entries at or after its position.

        Raises:
            WorkoutExerciseNotFoundError: If the parent is absent or disappears.
            WorkoutNotFoundError: If the parent workout is missing or belongs to another user.
            SetEntryValidationError: If the position exceeds count + 1.
            SetEntryCreationError: If creation raises SetEntryRepositoryError.

        Appending needs no shift. Database and row-mapping errors propagate;
        every failure before commit rolls back both shifting and insertion.
        """
        workout_exercise = self.workout_exercise_repo.get_by_id(set_entry_data.workout_exercise_id)
        if workout_exercise is None:
            raise WorkoutExerciseNotFoundError.not_found(set_entry_data.workout_exercise_id)

        require_owned_workout(self.workout_repo, user_id, workout_exercise.workout_id)

        with self._set_entry_transaction(set_entry_data.workout_exercise_id) as uow:
            count = len(uow.set_entry.list_by_workout_exercise(workout_exercise.id))
            set_number = set_entry_data.set_number
            if set_number > count + 1:
                raise SetEntryValidationError.invalid_set_number(set_number, count)
            if set_number <= count:
                uow.set_entry.shift_set_numbers(set_entry_data.workout_exercise_id, set_number, delta=1)

            try:
                set_entry = uow.set_entry.create(set_entry_data)
            except SetEntryRepositoryError as exc:
                raise SetEntryCreationError.create_failed() from exc
            uow.commit()
            return set_entry

    def get_by_id(self, user_id: int, set_entry_id: int) -> SetEntryPublic:
        """Return a set only after validating its full ownership chain.

        Args:
            user_id: Authenticated user ID.
            set_entry_id: Set entry to retrieve.

        Returns:
            The validated set entry after ownership succeeds.

        Raises:
            SetEntryNotFoundError: If the set is missing.
            WorkoutExerciseNotFoundError: If its parent exercise is missing.
            WorkoutNotFoundError: If its workout is missing or belongs to another user.
        """
        set_entry = self.set_entry_repo.get_by_id(set_entry_id)
        if set_entry is None:
            raise SetEntryNotFoundError.not_found(set_entry_id)

        workout_exercise = self.workout_exercise_repo.get_by_id(set_entry.workout_exercise_id)
        if workout_exercise is None:
            raise WorkoutExerciseNotFoundError.not_found(set_entry.workout_exercise_id)

        require_owned_workout(self.workout_repo, user_id, workout_exercise.workout_id)

        return set_entry

    def list_by_workout_exercise(self, user_id: int, workout_exercise_id: int) -> list[SetEntryPublic]:
        """Return an owned exercise's sets ordered by set number, then ID.

        Args:
            user_id: Authenticated user ID.
            workout_exercise_id: Parent workout exercise to list sets for.

        Returns:
            All matching sets, including an empty list for an exercise without sets.

        Raises:
            WorkoutExerciseNotFoundError: If the parent exercise is missing.
            WorkoutNotFoundError: If its workout is missing or belongs to another user.
        """
        workout_exercise = self.workout_exercise_repo.get_by_id(workout_exercise_id)
        if workout_exercise is None:
            raise WorkoutExerciseNotFoundError.not_found(workout_exercise_id)

        require_owned_workout(self.workout_repo, user_id, workout_exercise.workout_id)

        return self.set_entry_repo.list_by_workout_exercise(workout_exercise_id)

    def update(
        self, user_id: int, workout_exercise_id: int, set_entry_id: int, update_data: SetEntryUpdate
    ) -> SetEntryPublic:
        """Partially update an owned set, moving it within 1..count when requested.

        Args:
            user_id: Authenticated user ID.
            workout_exercise_id: Expected parent exercise ID.
            set_entry_id: Set entry to update.
            update_data: Validated changes; None-valued fields are ignored.

        Returns:
            The persisted set. Empty updates return its current values.

        Raises:
            SetEntryNotFoundError: If the set is absent or disappears during the update.
            WorkoutExerciseNotFoundError: If the parent is absent or disappears.
            WorkoutNotFoundError: If the workout is missing or belongs to another user.
            WorkoutExerciseValidationError: If the supplied parent ID does not match.
            SetEntryValidationError: If the position is unchanged or exceeds count.

        Re-read the current position after locking. Moving earlier shifts the
        inclusive range new..old - 1 by +1; moving later shifts old + 1..new
        by -1. Exclude the target set. All shifts and updates commit together.
        Repository, database, and row-mapping failures propagate and roll back.
        """
        set_entry = self.set_entry_repo.get_by_id(set_entry_id)
        if set_entry is None:
            raise SetEntryNotFoundError.not_found(set_entry_id)

        workout_exercise = self.workout_exercise_repo.get_by_id(set_entry.workout_exercise_id)
        if workout_exercise is None:
            raise WorkoutExerciseNotFoundError.not_found(set_entry.workout_exercise_id)

        require_owned_workout(self.workout_repo, user_id, workout_exercise.workout_id)

        if workout_exercise_id != workout_exercise.id:
            raise WorkoutExerciseValidationError.mismatched_ids(
                set_workout_exercise_id=set_entry.workout_exercise_id,
                requested_workout_exercise_id=workout_exercise_id,
            )

        with self._set_entry_transaction(workout_exercise_id) as uow:
            current = uow.set_entry.get_by_workout_exercise_and_id(workout_exercise_id, set_entry_id)
            if current is None:
                raise SetEntryNotFoundError.not_found(set_entry_id)
            old_set_number = current.set_number
            new_set_number = update_data.set_number
            if new_set_number is not None:
                if old_set_number == new_set_number:
                    raise SetEntryValidationError.identical_set_number(old_set_number, new_set_number)

                count = len(uow.set_entry.list_by_workout_exercise(workout_exercise.id))
                if new_set_number > count:
                    raise SetEntryValidationError.invalid_set_number(new_set_number, count)

                if new_set_number > old_set_number:
                    uow.set_entry.shift_set_numbers_in_range(
                        workout_exercise_id,
                        start=old_set_number + 1,
                        end=new_set_number,
                        delta=-1,
                        exclude_set_entry_id=set_entry_id,
                    )

                else:
                    uow.set_entry.shift_set_numbers_in_range(
                        workout_exercise_id,
                        start=new_set_number,
                        end=old_set_number - 1,
                        delta=1,
                        exclude_set_entry_id=set_entry_id,
                    )

            updated = uow.set_entry.update_in_workout_exercise(workout_exercise_id, set_entry_id, update_data)

            if updated is None:
                raise SetEntryNotFoundError.not_found(set_entry_id)

            uow.commit()
            return updated

    def delete(self, user_id: int, workout_exercise_id: int, set_entry_id: int) -> None:
        """Delete an owned set and close numbering gaps in the same transaction.

        Args:
            user_id: Authenticated user ID.
            workout_exercise_id: Expected parent exercise ID.
            set_entry_id: Set entry to delete.

        Raises:
            SetEntryNotFoundError: If the set is absent or disappears before deletion.
            WorkoutExerciseNotFoundError: If the parent is absent or disappears.
            WorkoutNotFoundError: If the workout is missing or belongs to another user.
            WorkoutExerciseValidationError: If the supplied parent ID does not match.
            SetEntryDeleteError: If deletion affects no row after the locked check.

        Normalize remaining sets to 1..count, including deleting the final set.
        Repository or database failures roll back deletion and normalization.
        """
        set_entry = self.set_entry_repo.get_by_id(set_entry_id)
        if set_entry is None:
            raise SetEntryNotFoundError.not_found(set_entry_id)

        workout_exercise = self.workout_exercise_repo.get_by_id(set_entry.workout_exercise_id)
        if workout_exercise is None:
            raise WorkoutExerciseNotFoundError.not_found(set_entry.workout_exercise_id)

        require_owned_workout(self.workout_repo, user_id, workout_exercise.workout_id)

        if workout_exercise_id != workout_exercise.id:
            raise WorkoutExerciseValidationError.mismatched_ids(
                set_workout_exercise_id=set_entry.workout_exercise_id,
                requested_workout_exercise_id=workout_exercise_id,
            )

        with self._set_entry_transaction(workout_exercise_id) as uow:
            current = uow.set_entry.get_by_workout_exercise_and_id(workout_exercise_id, set_entry_id)
            if current is None:
                raise SetEntryNotFoundError.not_found(set_entry_id)

            deleted = uow.set_entry.delete_in_workout_exercise(workout_exercise_id, set_entry_id)
            if not deleted:
                raise SetEntryDeleteError.delete_failed(set_entry_id)

            uow.set_entry.normalize_set_numbers(workout_exercise_id)

            uow.commit()
