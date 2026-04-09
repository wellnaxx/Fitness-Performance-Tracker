from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.params import Query

from dependencies.auth import get_current_user
from dependencies.providers import get_exercise_service
from schemas.exercise_schema import ExerciseCreate, ExercisePublic, ExerciseUpdate
from schemas.user_schema import UserInternal
from services.exercise_service import ExerciseService
from utils.errors import (
    ExerciseCreationError,
    ExerciseDeleteError,
    ExerciseNameAlreadyExistsError,
    ExerciseNotFoundError,
    ExerciseUpdateError,
)

exercise_router = APIRouter(prefix="/exercises", tags=["exercises"])


@exercise_router.post("/", response_model=ExercisePublic, status_code=status.HTTP_201_CREATED)
def create_exercise(
    exercise_data: ExerciseCreate,
    current_user: UserInternal = Depends(get_current_user),
    service: ExerciseService = Depends(get_exercise_service),
) -> ExercisePublic:
    """
    Create a new exercise for the authenticated user.
    """
    try:
        return service.create_exercise(exercise_data, current_user.id)
    except ExerciseNameAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ExerciseCreationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@exercise_router.get("/{exercise_id}", response_model=ExercisePublic, status_code=status.HTTP_200_OK)
def get_exercise_by_id(
    exercise_id: int,
    current_user: UserInternal = Depends(get_current_user),
    service: ExerciseService = Depends(get_exercise_service),
) -> ExercisePublic:
    """
    Retrieve an exercise by ID, ensuring it's visible to the user.
    """
    try:
        return service.get_visible_by_user(exercise_id, current_user.id)
    except ExerciseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@exercise_router.get("/", response_model=list[ExercisePublic], status_code=status.HTTP_200_OK)
def list_exercises(
    current_user: UserInternal = Depends(get_current_user),
    service: ExerciseService = Depends(get_exercise_service),
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum number of exercises to return.")] = 100,
    offset: Annotated[int, Query(ge=0, description="Number of exercises to skip.")] = 0,
    search: Annotated[str | None, Query(description="Search term for exercise names.")] = None,
    muscle_group: Annotated[str | None, Query(description="Filter by muscle group.")] = None,
    equipment: Annotated[str | None, Query(description="Filter by equipment.")] = None,
    is_compound: Annotated[bool | None, Query(description="Filter by compound exercises.")] = None,
    is_custom: Annotated[bool | None, Query(description="Filter by custom exercises.")] = None,
) -> list[ExercisePublic]:
    """
    List exercises visible to the user with optional filtering and pagination.
    """
    return service.list_visible_by_user(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        search=search,
        muscle_group=muscle_group,
        equipment=equipment,
        is_compound=is_compound,
        is_custom=is_custom,
    )


@exercise_router.patch("/{exercise_id}", response_model=ExercisePublic, status_code=status.HTTP_200_OK)
def update_exercise(
    exercise_id: int,
    update_data: ExerciseUpdate,
    current_user: UserInternal = Depends(get_current_user),
    service: ExerciseService = Depends(get_exercise_service),
) -> ExercisePublic:
    """
    Update an existing exercise if it belongs to the user.
    """
    try:
        return service.update_exercise(current_user.id, exercise_id, update_data)
    except ExerciseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ExerciseUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@exercise_router.delete("/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(
    exercise_id: int,
    current_user: UserInternal = Depends(get_current_user),
    service: ExerciseService = Depends(get_exercise_service),
) -> None:
    """
    Delete an existing exercise if it belongs to the user.
    """
    try:
        service.delete_exercise(current_user.id, exercise_id)
    except ExerciseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ExerciseDeleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
