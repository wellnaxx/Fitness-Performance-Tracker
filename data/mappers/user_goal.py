"""Database row validation and mapping for user goal."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

from core.errors.repository import UserGoalRowError
from data.validation import RowValidator
from schemas.user_goals_schema import UserGoalPublic

if TYPE_CHECKING:
    from datetime import date

_validator = RowValidator(UserGoalRowError)


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

    id_value = _validator.require_int(row.get("id"), "id")
    user_id_value = _validator.require_int(row.get("user_id"), "user_id")
    daily_calorie_target_value = _validator.require_int(row.get("daily_calorie_target"), "daily_calorie_target")
    protein_target_value = _validator.require_int(row.get("protein_target"), "protein_target")
    carbs_target_value = _validator.require_int(row.get("carbs_target"), "carbs_target")
    fat_target_value = _validator.require_int(row.get("fat_target"), "fat_target")
    weekly_workout_target_value = _validator.require_int(
        row.get("weekly_workout_target"), "weekly_workout_target"
    )
    target_body_weight_value = _validator.require_numeric(row.get("target_body_weight"), "target_body_weight")
    start_date_value = _validator.require_date(row.get("start_date"), "start_date")
    end_date_value = _validator.require_optional_date(row.get("end_date"), "end_date")
    is_active_value = _validator.require_bool(row.get("is_active"), "is_active")

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
