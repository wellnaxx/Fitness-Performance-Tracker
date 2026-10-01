"""Repository contract for UserGoals."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from schemas.user_goals_schema import UserGoalCreate, UserGoalPublic, UserGoalUpdate


class UserGoalsRepositoryPort(Protocol):
    """Persistence operations required by application consumers.

    Implementations preserve the documented ownership and filtering semantics
    and use the existing repository errors for persistence failures.
    """

    def create(self, user_id: int, goal_data: UserGoalCreate) -> UserGoalPublic:
        """Create a new goal for a specific user."""
        ...

    def get_by_user_and_id(self, user_id: int, goal_id: int) -> UserGoalPublic | None:
        """Retrieve a goal by its ID, but only if it belongs to the specified user."""
        ...

    def get_active_goal(self, user_id: int) -> UserGoalPublic | None:
        """Retrieve the currently active goal for a user."""
        ...

    def get_all(self, user_id: int, limit: int = 100, offset: int = 0) -> list[UserGoalPublic]:
        """Retrieve all goals for a specific user with pagination."""
        ...

    def update(self, goal_id: int, update_data: UserGoalUpdate) -> UserGoalPublic | None:
        """Partially update a goal by ID."""
        ...

    def deactivate_goal(self, goal_id: int) -> UserGoalPublic | None:
        """Mark a goal as inactive."""
        ...

    def activate_goal(self, user_id: int, goal_id: int) -> UserGoalPublic | None:
        """Mark a goal as active."""
        ...
