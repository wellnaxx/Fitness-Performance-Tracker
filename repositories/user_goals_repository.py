"""
User Goals Repository

This module handles all database interactions for the User Goal entity.
It translates between database rows (now dicts) and Pydantic models.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final, TypedDict

from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from schemas.user_goals_schema import UserGoalCreate, UserGoalPublic, UserGoalUpdate


class GoalRow(TypedDict):
    id: int
    user_id: int
    daily_calorie_target: int
    protein_target: int
    carbs_target: int
    fat_target: int
    weekly_workout_target: int
    target_body_weight: Decimal
    start_date: date
    end_date: date | None
    is_active: bool


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

    _BASE_SELECT: Final[str] = """
    SELECT
    id, user_id, daily_calorie_target,
    protein_target, carbs_target, fat_target,
    weekly_workout_target, target_body_weight,
    start_date, end_date, is_active
    FROM user_goals    
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
            RuntimeError: If the goal is inserted but cannot be retrieved afterwards.
        """

        sql = """
        INSERT INTO user_goals
        (user_id, daily_calorie_target, protein_target, carbs_target, fat_target,
         weekly_workout_target, target_body_weight, start_date, end_date, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
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
            raise RuntimeError("Failed to retrieve newly created goal")
        return goal

    def get_by_id(self, goal_id: int) -> UserGoalPublic | None:
        """
        Retrieve a goal by its database ID.

        Args:
            goal_id: Goal ID.

        Returns:
            UserGoalPublic if found, otherwise None.
        """

        sql = self._BASE_SELECT + " WHERE id = %s"
        row = fetch_one(sql, (goal_id,))
        if row is None:
            return None
        return self._row_to_goal(row)

    def get_by_user_and_id(self, user_id: int, goal_id: int) -> UserGoalPublic | None:
        """
        Retrieve a goal by its ID, but only if it belongs to the specified user.

        Args:
            user_id: Owner user ID.
            goal_id: Goal ID.

        Returns:
            UserGoalPublic if found and belongs to user, otherwise None.
        """

        sql = self._BASE_SELECT + " WHERE id = %s AND user_id = %s"
        row = fetch_one(sql, (goal_id, user_id))
        if row is None:
            return None
        return self._row_to_goal(row)

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

        sql = self._BASE_SELECT + " WHERE user_id = %s AND is_active = TRUE ORDER BY start_date DESC LIMIT 1"
        row = fetch_one(sql, (user_id,))
        if row is None:
            return None
        return self._row_to_goal(row)

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
        sql = self._BASE_SELECT + " WHERE user_id = %s ORDER BY start_date DESC, id DESC LIMIT %s OFFSET %s"
        rows = fetch_all(sql, (user_id, safe_limit, safe_offset))
        return [self._row_to_goal(row) for row in rows]

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
            ValueError: If no valid updatable fields were provided.
            ValueError: If any provided fields are not in the update whitelist.
        """

        fields = update_data.model_dump(exclude_none=True)

        if not fields:
            return self.get_by_id(goal_id)
        unknown = set(fields) - self._GOAL_UPDATE_WHITELIST
        if unknown:
            raise ValueError(f"Invalid fields: {', '.join(sorted(unknown))}")
        set_clause = ", ".join(f"{k} = %s" for k in fields)
        sql = f"UPDATE user_goals SET {set_clause} WHERE id = %s"
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

        sql = "UPDATE user_goals SET is_active = FALSE WHERE id = %s"
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

        sql = "UPDATE user_goals SET is_active = (id = %s) WHERE user_id = %s"
        execute_write(sql, (goal_id, user_id))
        return self.get_by_id(goal_id)

    @staticmethod
    def _parse_goal_row(row: dict[str, object]) -> GoalRow:
        """
        Validate and normalize a raw database row into a typed GoalRow structure.

        Args:
            row: Raw row dictionary returned from the database executor.

        Returns:
            GoalRow: Strongly typed intermediate representation.

        Raises:
            ValueError: If any expected field is missing or has an invalid type.
        """

        id_value = row.get("id")
        user_id_value = row.get("user_id")
        daily_calorie_target_value = row.get("daily_calorie_target")
        protein_target_value = row.get("protein_target")
        carbs_target_value = row.get("carbs_target")
        fat_target_value = row.get("fat_target")
        weekly_workout_target_value = row.get("weekly_workout_target")
        target_body_weight_value = row.get("target_body_weight")
        start_date_value = row.get("start_date")
        end_date_value = row.get("end_date")
        is_active_value = row.get("is_active")

        if not isinstance(id_value, int):
            raise ValueError("Invalid type for id")
        if not isinstance(user_id_value, int):
            raise ValueError("Invalid type for user_id")
        if not isinstance(daily_calorie_target_value, int):
            raise ValueError("Invalid type for daily_calorie_target")
        if not isinstance(protein_target_value, int):
            raise ValueError("Invalid type for protein_target")
        if not isinstance(carbs_target_value, int):
            raise ValueError("Invalid type for carbs_target")
        if not isinstance(fat_target_value, int):
            raise ValueError("Invalid type for fat_target")
        if not isinstance(weekly_workout_target_value, int):
            raise ValueError("Invalid type for weekly_workout_target")
        if not isinstance(target_body_weight_value, (Decimal, float, int)):
            raise ValueError("Invalid type for target_body_weight")
        if not isinstance(start_date_value, date):
            raise ValueError("Invalid type for start_date")
        if end_date_value is not None and not isinstance(end_date_value, date):
            raise ValueError("Invalid type for end_date")
        if not isinstance(is_active_value, bool):
            raise ValueError("Invalid type for is_active")

        return GoalRow(
            id=id_value,
            user_id=user_id_value,
            daily_calorie_target=daily_calorie_target_value,
            protein_target=protein_target_value,
            carbs_target=carbs_target_value,
            fat_target=fat_target_value,
            weekly_workout_target=weekly_workout_target_value,
            target_body_weight=Decimal(target_body_weight_value),
            start_date=start_date_value,
            end_date=end_date_value,
            is_active=is_active_value,
        )

    @classmethod
    def _row_to_goal(cls, row: dict[str, object]) -> UserGoalPublic:
        """
        Convert a raw database row into a validated UserGoalPublic model.

        Args:
            row: Raw row dictionary returned from the database executor.

        Returns:
            UserGoalPublic: Validated goal model.
        """

        user_goal_row = cls._parse_goal_row(row)
        return UserGoalPublic.model_validate(user_goal_row)
