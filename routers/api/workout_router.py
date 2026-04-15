from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.params import Query

from core.errors.workout import (
    WorkoutCreationError,
    WorkoutDeleteError,
    WorkoutNotFoundError,
    WorkoutUpdateError,
)
from dependencies.auth import get_current_user
from dependencies.providers import get_workout_service
from schemas.user_schema import UserInternal
from schemas.workout_schema import WorkoutCreate, WorkoutPublic, WorkoutUpdate
from services.workout_service import WorkoutService

workout_router = APIRouter(prefix="/workouts", tags=["workouts"])


@workout_router.post("/", status_code=status.HTTP_201_CREATED)
def create_workout(
    workout_data: WorkoutCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutService, Depends(get_workout_service)],
) -> WorkoutPublic:
    """
    Create a new workout for the authenticated user.
    """
    try:
        return service.create_workout(current_user.id, workout_data)
    except WorkoutCreationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@workout_router.get("/{workout_id}", status_code=status.HTTP_200_OK)
def get_workout_by_id(
    workout_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutService, Depends(get_workout_service)],
) -> WorkoutPublic:
    """
    Retrieve a workout by ID, ensuring it's visible to the user.
    """
    try:
        return service.get_visible_by_user(workout_id, current_user.id)
    except WorkoutNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@workout_router.get("/", status_code=status.HTTP_200_OK)
def list_workouts(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutService, Depends(get_workout_service)],
    search: Annotated[str | None, Query(min_length=1)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    date_from: Annotated[
        date | None, Query(description="Filter workouts from this date (inclusive).")
    ] = None,
    date_to: Annotated[
        date | None, Query(description="Filter workouts up to this date (inclusive).")
    ] = None,
) -> list[WorkoutPublic]:
    """
    List workouts visible to the authenticated user with pagination.
    """
    return service.list_visible_by_user(
        current_user.id, search=search, limit=limit, offset=offset, date_from=date_from, date_to=date_to
    )


@workout_router.patch("/{workout_id}", status_code=status.HTTP_200_OK)
def update_workout(
    workout_id: int,
    workout_data: WorkoutUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutService, Depends(get_workout_service)],
) -> WorkoutPublic:
    """
    Update a workout by ID, ensuring it's visible to the user.
    """
    try:
        return service.update_workout(workout_id, current_user.id, workout_data)
    except WorkoutNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WorkoutUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@workout_router.delete("/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workout(
    workout_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutService, Depends(get_workout_service)],
) -> None:
    """
    Delete a workout by ID, ensuring it's visible to the user.
    """
    try:
        service.delete_workout(workout_id, current_user.id)
    except WorkoutNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WorkoutDeleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
