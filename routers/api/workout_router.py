"""HTTP endpoints for workout operations."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.params import Path, Query

from dependencies.auth import get_current_user
from dependencies.pagination import get_pagination
from dependencies.providers import get_workout_service
from schemas.user_schema import UserInternal
from schemas.workout_schema import WorkoutCreate, WorkoutPublic, WorkoutUpdate
from services.workout_service import WorkoutService
from utils.pagination import PaginationParams

workout_router = APIRouter(
    prefix="/workouts",
    tags=["workouts"],
    responses={
        500: {"description": "Persistence failure; internal details are excluded from the response."},
        401: {"description": "Missing, invalid, expired, or revoked Bearer access token."},
    },
)


@workout_router.post("/", status_code=status.HTTP_201_CREATED)
def create_workout(
    workout_data: WorkoutCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutService, Depends(get_workout_service)],
) -> WorkoutPublic:
    """Create a new workout for the authenticated user.

    Args:
        workout_data: Validated workout creation or partial-update values.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The persisted record with its assigned ID (HTTP 201).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        WorkoutCreationError: HTTP 500. If creation fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.create(current_user.id, workout_data)


@workout_router.get(
    "/{workout_id}",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "If the record is missing or unowned."}},
)
def get_workout_by_id(
    workout_id: Annotated[int, Path(gt=0, description="Parent workout ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutService, Depends(get_workout_service)],
) -> WorkoutPublic:
    """Retrieve a workout by ID, ensuring it's visible to the user.

    Args:
        workout_id: Positive parent workout ID.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        WorkoutNotFoundError: HTTP 404. If the record is missing or unowned.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.get_by_id(current_user.id, workout_id)


@workout_router.get("/", status_code=status.HTTP_200_OK)
def list_workouts(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutService, Depends(get_workout_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    search: Annotated[str | None, Query(min_length=1)] = None,
    date_from: Annotated[date | None, Query(description="Filter workouts from this date (inclusive).")] = None,
    date_to: Annotated[date | None, Query(description="Filter workouts up to this date (inclusive).")] = None,
) -> list[WorkoutPublic]:
    """List workouts visible to the authenticated user with pagination.

    Args:
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.
        pagination: Shared limit/offset parameters: defaults 100/0, limit 1..1000, offset nonnegative.
        search: Optional text search for visible records.
        date_from: Optional inclusive lower date bound.
        date_to: Optional inclusive upper date bound.

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
        search=search,
        limit=pagination.limit,
        offset=pagination.offset,
        date_from=date_from,
        date_to=date_to,
    )


@workout_router.patch(
    "/{workout_id}",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "If the record is missing or unowned."}},
)
def update_workout(
    workout_id: Annotated[int, Path(gt=0, description="Parent workout ID.")],
    workout_data: WorkoutUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutService, Depends(get_workout_service)],
) -> WorkoutPublic:
    """Update a workout by ID, ensuring it's visible to the user.

    Args:
        workout_id: Positive parent workout ID.
        workout_data: Validated workout creation or partial-update values.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        WorkoutNotFoundError: HTTP 404. If the record is missing or unowned.
        WorkoutUpdateError: HTTP 500. If persistence fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.update(current_user.id, workout_id, workout_data)


@workout_router.delete(
    "/{workout_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "If the record is missing or unowned."}},
)
def delete_workout(
    workout_id: Annotated[int, Path(gt=0, description="Parent workout ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutService, Depends(get_workout_service)],
) -> None:
    """Delete a workout by ID, ensuring it's visible to the user.

    Args:
        workout_id: Positive parent workout ID.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        An empty response after successful completion (HTTP 204).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        WorkoutNotFoundError: HTTP 404. If the record is missing or unowned.
        WorkoutDeleteError: HTTP 500. If persistence fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    service.delete(current_user.id, workout_id)
