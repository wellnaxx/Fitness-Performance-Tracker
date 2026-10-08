"""Application contracts for explicit database transaction boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ports.repositories.user_goals_repository import UserGoalsRepositoryPort

if TYPE_CHECKING:
    from types import TracebackType


class UnitOfWorkUserGoalsRepositoryPort(UserGoalsRepositoryPort, Protocol):
    """Goal operations bound to one transaction, without independent commits."""

    def lock_for_user(self, user_id: int) -> bool:
        """Lock the user row to serialize goal changes; return False if absent."""
        ...


class UnitOfWorkPort(Protocol):
    """Commit explicitly; otherwise roll back when leaving the context."""

    @property
    def goals(self) -> UnitOfWorkUserGoalsRepositoryPort:
        """Return the goal repository belonging to the active transaction."""
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
