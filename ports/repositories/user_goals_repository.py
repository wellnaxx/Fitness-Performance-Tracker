"""Repository contract for UserGoals."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET

if TYPE_CHECKING:
    from schemas.user_goals_schema import UserGoalCreate, UserGoalPublic, UserGoalUpdate


class UserGoalsRepositoryPort(Protocol):
    """Persistence operations required by application consumers.

    Implementations preserve the documented ownership and filtering semantics
    and use the existing repository errors for persistence failures.
    """

    def create(self, user_id: int, goal_data: UserGoalCreate) -> UserGoalPublic:
        """Create a new goal for a specific user.

        Args:
            user_id: ID of the user who owns the goal.
            goal_data: Goal creation payload.

        Returns:
            UserGoalPublic: The newly created goal.

        Raises:
            UserGoalsRepositoryError: If the goal is inserted but cannot be retrieved afterwards.
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def get_by_user_and_id(self, user_id: int, goal_id: int) -> UserGoalPublic | None:
        """Retrieve a goal by its ID, but only if it belongs to the specified user.

        Args:
            user_id: Owner user ID.
            goal_id: Goal ID.

        Returns:
            UserGoalPublic if found and belongs to user, otherwise None.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def get_active_goal(self, user_id: int) -> UserGoalPublic | None:
        """Retrieve the currently active goal for a user.

        If multiple active goals exist unexpectedly, the most recent one by
        start_date is returned.

        Args:
            user_id: Owner user ID.

        Returns:
            UserGoalPublic if an active goal exists, otherwise None.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def get_all(
        self,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
    ) -> list[UserGoalPublic]:
        """Retrieve all goals for a specific user with pagination.

        Args:
            user_id: Owner user ID.
            limit: Maximum number of results to return.
            offset: Number of rows to skip.

        Returns:
            A list of the user's goals ordered from newest to oldest.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def update(self, goal_id: int, update_data: UserGoalUpdate) -> UserGoalPublic | None:
        """Partially update a goal by ID.

        Only fields in the repository whitelist are applied. Fields with value None
        are ignored.

        Args:
            goal_id: Goal ID to update.
            update_data: Partial update payload.

        Returns:
            The updated goal if it exists, otherwise None.

        Raises:
            UserGoalsRepositoryError: If any provided fields are not in the update whitelist.
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def deactivate_goal(self, goal_id: int) -> UserGoalPublic | None:
        """Mark a goal as inactive.

        Args:
            goal_id: Goal ID.

        Returns:
            The updated goal if it exists, otherwise None.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def activate_goal(self, user_id: int, goal_id: int) -> UserGoalPublic | None:
        """Mark a goal as active.

        Args:
            user_id: User ID.
            goal_id: Goal ID.

        Returns:
            The updated goal if it exists, otherwise None.

        Notes:
            Atomically set one goal as active and deactivate all others for the user.
            Ensures that at most one goal is active per user.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...
