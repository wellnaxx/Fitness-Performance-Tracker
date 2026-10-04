from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.params import Query

from dependencies.auth import get_current_user
from dependencies.pagination import get_pagination
from dependencies.providers import get_exercise_service
from schemas.exercise_schema import ExerciseCreate, ExercisePublic, ExerciseUpdate
from schemas.user_schema import UserInternal
from services.exercise_service import ExerciseService
from utils.pagination import PaginationParams

exercise_router = APIRouter(prefix="/exercises", tags=["exercises"])


@exercise_router.post("/", status_code=status.HTTP_201_CREATED)
def create_exercise(
    exercise_data: ExerciseCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[ExerciseService, Depends(get_exercise_service)],
) -> ExercisePublic:
    """
    Create a new exercise for the authenticated user.
    """
    return service.create_exercise(exercise_data, current_user.id)


@exercise_router.get("/{exercise_id}", status_code=status.HTTP_200_OK)
def get_exercise_by_id(
    exercise_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[ExerciseService, Depends(get_exercise_service)],
) -> ExercisePublic:
    """
    Retrieve an exercise by ID, ensuring it's visible to the user.
    """
    return service.get_visible_by_user(exercise_id, current_user.id)


@exercise_router.get("/", status_code=status.HTTP_200_OK)
def list_exercises(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[ExerciseService, Depends(get_exercise_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
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
        limit=pagination.limit,
        offset=pagination.offset,
        search=search,
        muscle_group=muscle_group,
        equipment=equipment,
        is_compound=is_compound,
        is_custom=is_custom,
    )


@exercise_router.patch("/{exercise_id}", status_code=status.HTTP_200_OK)
def update_exercise(
    exercise_id: int,
    update_data: ExerciseUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[ExerciseService, Depends(get_exercise_service)],
) -> ExercisePublic:
    """
    Update an existing exercise if it belongs to the user.
    """
    return service.update_exercise(current_user.id, exercise_id, update_data)


@exercise_router.delete("/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(
    exercise_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[ExerciseService, Depends(get_exercise_service)],
) -> None:
    """
    Delete an existing exercise if it belongs to the user.
    """
    service.delete_exercise(current_user.id, exercise_id)
