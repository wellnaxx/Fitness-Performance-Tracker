"""
User Goals Repository

This module handles all database interactions for the User Goal entity.
It delegates database row validation and conversion to the dedicated mapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from core.errors.repository import UserGoalsRepositoryError
from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from data.mappers.user_goal import map_user_goal
from data.queries import QUERIES

if TYPE_CHECKING:
    from schemas.user_goals_schema import UserGoalCreate, UserGoalPublic, UserGoalUpdate


class UserGoalsRepository:
    """
    Repository for user goal database operations.

    Responsibilities:
    - Execute SQL queries related to user goals
    - Convert database rows into validated Pydantic models
    - Provide persistence operations for creating, reading, and updating goals

    Notes:
    - Business rules such as 'only one active goal per user' should be enforced
      in the service layer, not in this repository.
    """

    _GOAL_UPDATE_WHITELIST: Final[set[str]] = {
        "daily_calorie_target",
        "protein_target",
        "carbs_target",
        "fat_target",
        "weekly_workout_target",
        "target_body_weight",
        "start_date",
        "end_date",
        "is_active",
    }

    def create(self, user_id: int, goal_data: UserGoalCreate) -> UserGoalPublic:
        """
        Create a new goal for a specific user.

        Args:
            user_id: ID of the user who owns the goal.
            goal_data: Goal creation payload.

        Returns:
            UserGoalPublic: The newly created goal.

        Raises:
            UserGoalsRepositoryError: If the goal is inserted but cannot be retrieved afterwards.
        """

        sql = QUERIES.user_goals.create
        goal_id = execute_insert(
            sql,
            (
                user_id,
                goal_data.daily_calorie_target,
                goal_data.protein_target,
                goal_data.carbs_target,
                goal_data.fat_target,
                goal_data.weekly_workout_target,
                goal_data.target_body_weight,
                goal_data.start_date,
                goal_data.end_date,
                goal_data.is_active,
            ),
        )
        goal = self.get_by_id(goal_id)
        if goal is None:
            raise UserGoalsRepositoryError.inserted_missing(goal_id)
        return goal

    def get_by_id(self, goal_id: int) -> UserGoalPublic | None:
        """
        Retrieve a goal by its database ID.

        Args:
            goal_id: Goal ID.

        Returns:
            UserGoalPublic if found, otherwise None.
        """

        sql = QUERIES.user_goals.get_by_id
        row = fetch_one(sql, (goal_id,))
        if row is None:
            return None
        return map_user_goal(row)

    def get_by_user_and_id(self, user_id: int, goal_id: int) -> UserGoalPublic | None:
        """
        Retrieve a goal by its ID, but only if it belongs to the specified user.

        Args:
            user_id: Owner user ID.
            goal_id: Goal ID.

        Returns:
            UserGoalPublic if found and belongs to user, otherwise None.
        """

        sql = QUERIES.user_goals.get_by_user_and_id
        row = fetch_one(sql, (goal_id, user_id))
        if row is None:
            return None
        return map_user_goal(row)

    def get_active_goal(self, user_id: int) -> UserGoalPublic | None:
        """
        Retrieve the currently active goal for a user.

        If multiple active goals exist unexpectedly, the most recent one by
        start_date is returned.

        Args:
            user_id: Owner user ID.

        Returns:
            UserGoalPublic if an active goal exists, otherwise None.
        """

        sql = QUERIES.user_goals.get_active_goal
        row = fetch_one(sql, (user_id,))
        if row is None:
            return None
        return map_user_goal(row)

    def get_all(self, user_id: int, limit: int = 100, offset: int = 0) -> list[UserGoalPublic]:
        """
        Retrieve all goals for a specific user with pagination.

        Args:
            user_id: Owner user ID.
            limit: Maximum number of results to return.
            offset: Number of rows to skip.

        Returns:
            A list of the user's goals ordered from newest to oldest.
        """

        safe_limit = max(1, min(limit, 1000))  # Enforce reasonable limits
        safe_offset = max(0, offset)
        sql = QUERIES.user_goals.get_all
        rows = fetch_all(sql, (user_id, safe_limit, safe_offset))
        return [map_user_goal(row) for row in rows]

    def update(self, goal_id: int, update_data: UserGoalUpdate) -> UserGoalPublic | None:
        """
        Partially update a goal by ID.

        Only fields in the repository whitelist are applied. Fields with value None
        are ignored.

        Args:
            goal_id: Goal ID to update.
            update_data: Partial update payload.

        Returns:
            The updated goal if it exists, otherwise None.

        Raises:
            UserGoalsRepositoryError: If any provided fields are not in the update whitelist.
        """

        fields = update_data.model_dump(exclude_none=True)

        if not fields:
            return self.get_by_id(goal_id)
        unknown = set(fields) - self._GOAL_UPDATE_WHITELIST
        if unknown:
            raise UserGoalsRepositoryError.invalid_update_fields(unknown)
        set_clause = ", ".join(f"{k} = %s" for k in fields)
        sql = QUERIES.user_goals.update.format(set_clause=set_clause)
        execute_write(sql, (*fields.values(), goal_id))
        return self.get_by_id(goal_id)

    def deactivate_goal(self, goal_id: int) -> UserGoalPublic | None:
        """
        Mark a goal as inactive.

        Args:
            goal_id: Goal ID.

        Returns:
            The updated goal if it exists, otherwise None.
        """

        sql = QUERIES.user_goals.deactivate_goal
        execute_write(sql, (goal_id,))
        return self.get_by_id(goal_id)

    def activate_goal(self, user_id: int, goal_id: int) -> UserGoalPublic | None:
        """
        Mark a goal as active.

        Args:
            user_id: User ID.
            goal_id: Goal ID.

        Returns:
            The updated goal if it exists, otherwise None.

        Notes:
            Atomically set one goal as active and deactivate all others for the user.
            Ensures that at most one goal is active per user.
        """

        sql = QUERIES.user_goals.activate_goal
        execute_write(sql, (goal_id, user_id))
        return self.get_by_id(goal_id)
