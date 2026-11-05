"""Ownership checks shared by services that operate within a workout."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.errors.workout import WorkoutNotFoundError

if TYPE_CHECKING:
    from ports.repositories.workout_repository import WorkoutRepositoryPort
    from schemas.workout_schema import WorkoutPublic

logger = logging.getLogger(__name__)


def require_owned_workout(
    workout_repo: WorkoutRepositoryPort,
    user_id: int,
    workout_id: int,
) -> WorkoutPublic:
    """Return the user's workout or raise WorkoutNotFoundError if inaccessible."""
    workout = workout_repo.get_by_user_and_id(user_id, workout_id)
    if workout is None:
        logger.warning("Workout with ID %s not found or not visible to user %s.", workout_id, user_id)
        raise WorkoutNotFoundError.not_accessible(workout_id=workout_id)
    return workout
