"""Application contracts for explicit database transaction boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ports.repositories.set_entry_repository import SetEntryRepositoryPort
from ports.repositories.user_goals_repository import UserGoalsRepositoryPort

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
