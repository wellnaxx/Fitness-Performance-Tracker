"""Ownership checks shared by services that operate within a workout or meal."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.meal import MealNotFoundError
from core.errors.workout import WorkoutNotFoundError

if TYPE_CHECKING:
    from logging import Logger

    from ports.repositories.meal_repository import MealRepositoryPort
    from ports.repositories.workout_repository import WorkoutRepositoryPort
    from schemas.meal_schema import MealPublic
    from schemas.workout_schema import WorkoutPublic


def require_owned_workout(
    workout_repo: WorkoutRepositoryPort,
    user_id: int,
    workout_id: int,
    *,
    logger: Logger,
) -> WorkoutPublic:
    """Retrieve an owned workout before accessing its child records.

    Args:
        workout_repo: Repository providing a user-scoped lookup.
        user_id: Authenticated user ID.
        workout_id: Requested parent workout ID.
        logger: Calling service's logger for ownership rejections.

    Returns:
        The workout belonging to the authenticated user.

    Raises:
        WorkoutNotFoundError: If the workout is missing or unowned.
        DatabaseError: If the lookup fails.
        RowValidationError: If the stored workout row is invalid.
        WorkoutRepositoryError: If the repository reports a lookup failure.
    """
    workout = workout_repo.get_by_user_and_id(user_id, workout_id)
    if workout is None:
        logger.warning("Workout with ID %s not found or not visible to user %s.", workout_id, user_id)
        raise WorkoutNotFoundError.not_accessible(workout_id=workout_id)
    return workout


def require_owned_meal(
    meal_repo: MealRepositoryPort, user_id: int, meal_id: int, *, logger: Logger
) -> MealPublic:
    """Retrieve an owned meal before accessing its child items.

    Args:
        meal_repo: Repository providing a user-scoped meal lookup.
        user_id: Authenticated user ID.
        meal_id: Requested parent meal ID.
        logger: Calling service's logger for ownership rejections.

    Returns:
        The meal belonging to the authenticated user.

    Raises:
        MealNotFoundError: If the meal is missing or belongs to another user.
        DatabaseError: If the database lookup fails.
        RowValidationError: If the stored meal row is invalid.
        MealRepositoryError: If the repository reports a lookup failure.
    """
    meal = meal_repo.get_by_user_and_id(user_id, meal_id)
    if meal is None:
        logger.warning("Meal with ID %s not found or not visible to user %s.", meal_id, user_id)
        raise MealNotFoundError.not_accessible(meal_id=meal_id)
    return meal
