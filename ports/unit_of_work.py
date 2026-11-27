"""Application contracts for explicit database transaction boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ports.repositories.set_entry_repository import SetEntryRepositoryPort
from ports.repositories.user_goals_repository import UserGoalsRepositoryPort
from ports.repositories.workout_exercise_repository import WorkoutExerciseRepositoryPort

if TYPE_CHECKING:
    from types import TracebackType


class UnitOfWorkUserGoalsRepositoryPort(UserGoalsRepositoryPort, Protocol):
    """Goal operations bound to one transaction, without independent commits."""

    def lock_for_user(self, user_id: int) -> bool:
        """Lock the user row to serialize goal changes; return False if absent."""
        ...


class UnitOfWorkSetEntryRepositoryPort(SetEntryRepositoryPort, Protocol):
    """Set-entry operations sharing one cursor and never committing independently."""

    def lock_for_workout_exercise(self, workout_exercise_id: int) -> bool:
        """Lock the parent row, including an exercise without sets.

        Return False if the parent is missing. Ownership must be checked by the
        service before locking. Cooperating set writers use the same parent lock
        to serialize counting, shifting, updates, and deletion.
        """
        ...


class UnitOfWorkWorkoutExerciseRepositoryPort(WorkoutExerciseRepositoryPort, Protocol):
    """Workout-exercise operations sharing the unit of work's transaction."""

    def lock_for_workout(self, user_id: int, workout_id: int) -> bool:
        """Authorize and lock the parent before any child lookup or position check.

        Args:
            user_id: Authenticated owner ID.
            workout_id: Requested workout ID.

        Returns:
            True if the owned workout is locked until transaction completion;
            False for missing, global, or foreign-owned workouts. Empty workouts
            are locked too, serializing all cooperating ordering writers.

        Raises:
            DatabaseError: If the lock query fails.
        """
        ...

    def lock_visible_exercise(self, user_id: int, exercise_id: int) -> bool:
        """Keep a visible catalog exercise stable until the write completes.

        Args:
            user_id: Authenticated owner ID.
            exercise_id: Exercise to add or use as a replacement.

        Returns:
            True if a global or user-owned exercise is locked for shared access;
            False if it is missing or owned by another user. The lock prevents
            deletion or changes to visibility during the transaction.

        Raises:
            DatabaseError: If the lock query fails.
        """
        ...


class UnitOfWorkPort(Protocol):
    """Commit explicitly; otherwise roll back when leaving the context."""

    @property
    def goals(self) -> UnitOfWorkUserGoalsRepositoryPort:
        """Return the goal repository belonging to the active transaction."""
        ...

    @property
    def set_entry(self) -> UnitOfWorkSetEntryRepositoryPort:
        """Return the active transaction's set repository, including ordering operations."""
        ...

    @property
    def workout_exercise(self) -> UnitOfWorkWorkoutExerciseRepositoryPort:
        """Return the active transaction's workout-exercise repository and locks."""
        ...

    def __enter__(self) -> UnitOfWorkPort:
        """Open a transaction and its repositories."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Roll back uncommitted work and close resources, preserving errors."""
        ...

    def commit(self) -> None:
        """Commit all changes; call only after the entire operation succeeds."""
        ...

    def rollback(self) -> None:
        """Discard uncommitted changes."""
        ...
