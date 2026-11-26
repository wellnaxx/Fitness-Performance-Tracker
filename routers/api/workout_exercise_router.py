"""HTTP endpoints for workout exercise operations."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.params import Path

from dependencies.auth import get_current_user
from dependencies.providers import get_workout_exercise_service
from schemas.user_schema import UserInternal
from schemas.workout_exercises_schema import (
    WorkoutExerciseCreate,
    WorkoutExercisePublic,
    WorkoutExerciseUpdate,
)
from services.workout_exercise_service import WorkoutExerciseService

workout_exercise_router = APIRouter(
    prefix="/workouts/{workout_id}/exercises",
    tags=["workout_exercises"],
    responses={
        500: {"description": "Persistence failure; internal details are excluded from the response."},
        401: {"description": "Missing, invalid, expired, or revoked Bearer access token."},
    },
)


@workout_exercise_router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "The workout or an exercise record is missing or inaccessible."},
        400: {"description": "If the position is outside the permitted range."},
    },
)
def create_workout_exercise(
    workout_id: Annotated[int, Path(gt=0, description="Parent workout ID.")],
    workout_exercise_data: WorkoutExerciseCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutExerciseService, Depends(get_workout_exercise_service)],
) -> WorkoutExercisePublic:
    """Add a new exercise to a workout.

    Args:
        workout_id: Positive parent workout ID.
        workout_exercise_data: Validated exercise reference and position within the parent workout.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The persisted record with its assigned ID (HTTP 201).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        WorkoutNotFoundError: HTTP 404. If the parent workout is missing or unowned.
        ExerciseNotFoundError: HTTP 404. If the exercise reference is not visible.
        WorkoutExerciseValidationError: HTTP 400. If the position is outside the permitted range.
        WorkoutExerciseCreationError: HTTP 500. If persistence fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.create(current_user.id, workout_id, workout_exercise_data)


@workout_exercise_router.get(
    "/{workout_exercise_id}",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "The workout or an exercise record is missing or inaccessible."}},
)
def get_workout_exercise_by_id(
    workout_id: Annotated[int, Path(gt=0, description="Parent workout ID.")],
    workout_exercise_id: Annotated[int, Path(gt=0, description="Parent workout exercise ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutExerciseService, Depends(get_workout_exercise_service)],
) -> WorkoutExercisePublic:
    """Retrieve a workout exercise by ID, ensuring it's visible to the user.

    Args:
        workout_id: Positive parent workout ID.
        workout_exercise_id: Positive parent workout exercise ID.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        WorkoutNotFoundError: HTTP 404. If the parent workout is missing or unowned.
        WorkoutExerciseNotFoundError: HTTP 404. If the entry is absent from the workout.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.get_by_id(current_user.id, workout_id, workout_exercise_id)


@workout_exercise_router.get(
    "/",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "The workout or an exercise record is missing or inaccessible."}},
)
def list_workout_exercises(
    workout_id: Annotated[int, Path(gt=0, description="Parent workout ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutExerciseService, Depends(get_workout_exercise_service)],
) -> list[WorkoutExercisePublic]:
    """List exercises in a workout that are visible to the user.

    Args:
        workout_id: Positive parent workout ID.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        Matching records in repository order, or [] when none match (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        WorkoutNotFoundError: HTTP 404. If the parent workout is missing or unowned.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.list_by_workout(current_user.id, workout_id)


@workout_exercise_router.patch(
    "/{workout_exercise_id}",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "The workout or an exercise record is missing or inaccessible."},
        400: {"description": "If the position is outside the permitted range."},
    },
)
def update_workout_exercise(
    workout_id: Annotated[int, Path(gt=0, description="Parent workout ID.")],
    workout_exercise_id: Annotated[int, Path(gt=0, description="Parent workout exercise ID.")],
    update_data: WorkoutExerciseUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutExerciseService, Depends(get_workout_exercise_service)],
) -> WorkoutExercisePublic:
    """Update a workout exercise, ensuring it's visible to the user.

    Args:
        workout_id: Positive parent workout ID.
        workout_exercise_id: Positive parent workout exercise ID.
        update_data: Validated partial changes; omitted and null fields preserve stored values.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        WorkoutNotFoundError: HTTP 404. If the parent workout is missing or unowned.
        WorkoutExerciseNotFoundError: HTTP 404. If the entry is absent from the workout.
        ExerciseNotFoundError: HTTP 404. If the exercise reference is not visible.
        WorkoutExerciseValidationError: HTTP 400. If the position is outside the permitted range.
        WorkoutExerciseUpdateError: HTTP 500. If persistence fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.update(current_user.id, workout_id, workout_exercise_id, update_data)


@workout_exercise_router.delete(
    "/{workout_exercise_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "The workout or an exercise record is missing or inaccessible."}},
)
def delete_workout_exercise(
    workout_id: Annotated[int, Path(gt=0, description="Parent workout ID.")],
    workout_exercise_id: Annotated[int, Path(gt=0, description="Parent workout exercise ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutExerciseService, Depends(get_workout_exercise_service)],
) -> None:
    """Delete a workout exercise, ensuring it's visible to the user.

    Args:
        workout_id: Positive parent workout ID.
        workout_exercise_id: Positive parent workout exercise ID.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        An empty response after successful completion (HTTP 204).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        WorkoutNotFoundError: HTTP 404. If the parent workout is missing or unowned.
        WorkoutExerciseNotFoundError: HTTP 404. If the entry is absent from the workout.
        WorkoutExerciseDeleteError: HTTP 500. If persistence fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    service.delete(current_user.id, workout_id, workout_exercise_id)
