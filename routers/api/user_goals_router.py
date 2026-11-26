"""HTTP endpoints for user goals operations."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.params import Path

from core.errors.goals import UserGoalNotFoundError
from dependencies.auth import get_current_user
from dependencies.pagination import get_pagination
from dependencies.providers import get_user_goals_service
from schemas.user_goals_schema import (
    UserGoalCreate,
    UserGoalPublic,
    UserGoalUpdate,
)
from schemas.user_schema import UserInternal
from services.user_goals_service import UserGoalsService
from utils.pagination import PaginationParams

user_goals_router = APIRouter(
    prefix="/goals",
    tags=["goals"],
    responses={
        500: {"description": "Persistence failure; internal details are excluded from the response."},
        401: {"description": "Missing, invalid, expired, or revoked Bearer access token."},
    },
)


@user_goals_router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    responses={404: {"description": "If the owner disappears before locking."}},
)
def create_goal(
    goal_data: UserGoalCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    """Create a goal for the authenticated user.

    Args:
        goal_data: Validated goal targets, date range, and initial active state.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The persisted record with its assigned ID (HTTP 201).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        UserNotFoundError: HTTP 404. If the owner disappears before locking.
        UserGoalCreationError: HTTP 500. If creation fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.create(current_user.id, goal_data)


@user_goals_router.get(
    "/current",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "If no requested owned goal is available."}},
)
def get_current_goal(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    """Retrieve the user's active goal.

    Args:
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        UserGoalNotFoundError: HTTP 404. If no requested owned goal is available.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    goal = service.get_current(current_user.id)
    if goal is None:
        raise UserGoalNotFoundError.no_active_goal()
    return goal


@user_goals_router.get(
    "/history",
    status_code=status.HTTP_200_OK,
)
def get_goal_history(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> list[UserGoalPublic]:
    """List the user's goal history.

    Args:
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.
        pagination: Shared limit/offset parameters: defaults 100/0, limit 1..1000, offset nonnegative.

    Returns:
        Matching records in repository order, or [] when none match (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.list_by_user(user_id=current_user.id, limit=pagination.limit, offset=pagination.offset)


@user_goals_router.get(
    "/{goal_id}",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "If no requested owned goal is available."}},
)
def get_goal_by_id(
    goal_id: Annotated[int, Path(gt=0, description="Goal ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    """Retrieve one owned goal.

    Args:
        goal_id: Positive goal ID.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        UserGoalNotFoundError: HTTP 404. If no requested owned goal is available.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.get_by_id(current_user.id, goal_id)


@user_goals_router.patch(
    "/{goal_id}",
    status_code=status.HTTP_200_OK,
    responses={
        404: {
            "description": "If the owner disappears before locking. If no requested owned goal is available."
        },
        400: {"description": "If the resulting date range is invalid."},
    },
)
def update_goal(
    goal_id: Annotated[int, Path(gt=0, description="Goal ID.")],
    update_data: UserGoalUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    """Partially update an owned goal.

    Args:
        goal_id: Positive goal ID.
        update_data: Validated partial changes; omitted and null fields preserve stored values.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        UserNotFoundError: HTTP 404. If the owner disappears before locking.
        UserGoalNotFoundError: HTTP 404. If no requested owned goal is available.
        UserGoalValidationError: HTTP 400. If the resulting date range is invalid.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.update(current_user.id, goal_id, update_data)


@user_goals_router.post(
    "/{goal_id}/deactivate",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "If the owner disappears before locking. If no requested owned goal is available."}
    },
)
def deactivate_goal(
    goal_id: Annotated[int, Path(gt=0, description="Goal ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    """Deactivate an owned goal.

    Args:
        goal_id: Positive goal ID.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        UserNotFoundError: HTTP 404. If the owner disappears before locking.
        UserGoalNotFoundError: HTTP 404. If no requested owned goal is available.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.deactivate_goal(current_user.id, goal_id)


@user_goals_router.post(
    "/{goal_id}/activate",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "If the owner disappears before locking. If no requested owned goal is available."}
    },
)
def activate_goal(
    goal_id: Annotated[int, Path(gt=0, description="Goal ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    """Activate a goal and deactivate any previous active goal atomically.

    Args:
        goal_id: Positive goal ID.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        UserNotFoundError: HTTP 404. If the owner disappears before locking.
        UserGoalNotFoundError: HTTP 404. If no requested owned goal is available.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.activate_goal(current_user.id, goal_id)
