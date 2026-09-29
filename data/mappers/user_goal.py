"""Database row validation and mapping for user goal."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TypedDict

from core.errors.repository import UserGoalRowError
from schemas.user_goals_schema import UserGoalPublic


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


def _parse_goal_row(row: dict[str, object]) -> GoalRow:
    """
    Validate and normalize a raw database row into a typed GoalRow structure.

    Args:
        row: Raw row dictionary returned from the database executor.

    Returns:
        GoalRow: Strongly typed intermediate representation.

    Raises:
        UserGoalRowError: If any expected field is missing or has an invalid type.
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
        raise UserGoalRowError.invalid_type("id", "int")
    if not isinstance(user_id_value, int):
        raise UserGoalRowError.invalid_type("user_id", "int")
    if not isinstance(daily_calorie_target_value, int):
        raise UserGoalRowError.invalid_type("daily_calorie_target", "int")
    if not isinstance(protein_target_value, int):
        raise UserGoalRowError.invalid_type("protein_target", "int")
    if not isinstance(carbs_target_value, int):
        raise UserGoalRowError.invalid_type("carbs_target", "int")
    if not isinstance(fat_target_value, int):
        raise UserGoalRowError.invalid_type("fat_target", "int")
    if not isinstance(weekly_workout_target_value, int):
        raise UserGoalRowError.invalid_type("weekly_workout_target", "int")
    if not isinstance(target_body_weight_value, (Decimal, float, int)):
        raise UserGoalRowError.invalid_type("target_body_weight", "numeric")
    if not isinstance(start_date_value, date):
        raise UserGoalRowError.invalid_type("start_date", "date")
    if end_date_value is not None and not isinstance(end_date_value, date):
        raise UserGoalRowError.invalid_type("end_date", "date | None")
    if not isinstance(is_active_value, bool):
        raise UserGoalRowError.invalid_type("is_active", "bool")

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


def map_user_goal(row: dict[str, object]) -> UserGoalPublic:
    """
    Convert a raw database row into a validated UserGoalPublic model.

    Args:
        row: Raw row dictionary returned from the database executor.

    Returns:
        UserGoalPublic: Validated goal model.
    """

    user_goal_row = _parse_goal_row(row)
    return UserGoalPublic.model_validate(user_goal_row)
