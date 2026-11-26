"""HTTP endpoints for exercise operations."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.params import Path, Query

from dependencies.auth import get_current_user
from dependencies.pagination import get_pagination
from dependencies.providers import get_exercise_service
from schemas.exercise_schema import ExerciseCreate, ExercisePublic, ExerciseUpdate
from schemas.user_schema import UserInternal
from services.exercise_service import ExerciseService
from utils.pagination import PaginationParams

exercise_router = APIRouter(
    prefix="/exercises",
    tags=["exercises"],
    responses={
        500: {"description": "Persistence failure; internal details are excluded from the response."},
        401: {"description": "Missing, invalid, expired, or revoked Bearer access token."},
    },
)


@exercise_router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "If another visible exercise uses the requested name."}},
)
def create_exercise(
    exercise_data: ExerciseCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[ExerciseService, Depends(get_exercise_service)],
) -> ExercisePublic:
    """Create a new exercise for the authenticated user.

    Args:
        exercise_data: Validated values for a new custom exercise.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The persisted record with its assigned ID (HTTP 201).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        ExerciseNameAlreadyExistsError: HTTP 409. If another visible exercise uses the requested name.
        ExerciseCreationError: HTTP 500. If creation fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.create(current_user.id, exercise_data)


@exercise_router.get(
    "/{exercise_id}",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "If the exercise is missing or not visible."}},
)
def get_exercise_by_id(
    exercise_id: Annotated[int, Path(gt=0, description="Exercise ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[ExerciseService, Depends(get_exercise_service)],
) -> ExercisePublic:
    """Retrieve an exercise by ID, ensuring it's visible to the user.

    Args:
        exercise_id: Positive exercise ID.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        ExerciseNotFoundError: HTTP 404. If the exercise is missing or not visible.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.get_by_id(current_user.id, exercise_id)


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
    """List exercises visible to the user with optional filtering and pagination.

    Args:
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.
        pagination: Shared limit/offset parameters: defaults 100/0, limit 1..1000, offset nonnegative.
        search: Optional text search for visible records.
        muscle_group: Optional muscle-group filter.
        equipment: Optional equipment filter.
        is_compound: Optional compound-exercise filter; False is a meaningful filter.
        is_custom: Optional custom-exercise filter; False is a meaningful filter.

    Returns:
        Matching records in repository order, or [] when none match (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.list_by_user(
        user_id=current_user.id,
        limit=pagination.limit,
        offset=pagination.offset,
        search=search,
        muscle_group=muscle_group,
        equipment=equipment,
        is_compound=is_compound,
        is_custom=is_custom,
    )


@exercise_router.patch(
    "/{exercise_id}",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "If the exercise is missing or unowned."},
        409: {"description": "If another visible exercise uses the requested name."},
    },
)
def update_exercise(
    exercise_id: Annotated[int, Path(gt=0, description="Exercise ID.")],
    update_data: ExerciseUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[ExerciseService, Depends(get_exercise_service)],
) -> ExercisePublic:
    """Update an existing exercise if it belongs to the user.

    Args:
        exercise_id: Positive exercise ID.
        update_data: Validated partial changes; omitted and null fields preserve stored values.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        ExerciseNotFoundError: HTTP 404. If the exercise is missing or unowned.
        ExerciseNameAlreadyExistsError: HTTP 409. If another visible exercise uses the requested name.
        ExerciseUpdateError: HTTP 500. If persistence fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.update(current_user.id, exercise_id, update_data)


@exercise_router.delete(
    "/{exercise_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "If missing, unowned, or disappearing during deletion."},
        400: {"description": "If deletion of a predefined exercise is requested."},
    },
)
def delete_exercise(
    exercise_id: Annotated[int, Path(gt=0, description="Exercise ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[ExerciseService, Depends(get_exercise_service)],
) -> None:
    """Delete an existing exercise if it belongs to the user.

    Args:
        exercise_id: Positive exercise ID.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        An empty response after successful completion (HTTP 204).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        ExerciseNotFoundError: HTTP 404. If missing, unowned, or disappearing during deletion.
        ExerciseValidationError: HTTP 400. If deletion of a predefined exercise is requested.
        ExerciseDeleteError: HTTP 500. If persistence fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    service.delete(current_user.id, exercise_id)
