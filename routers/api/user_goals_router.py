from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.errors.goals import (
    UserGoalCreationError,
    UserGoalNotFoundError,
    UserGoalValidationError,
)
from dependencies.auth import get_current_user
from dependencies.providers import get_user_goals_service
from schemas.user_goals_schema import (
    UserGoalCreate,
    UserGoalPublic,
    UserGoalUpdate,
)
from schemas.user_schema import UserInternal
from services.user_goals_service import UserGoalsService

user_goals_router = APIRouter(prefix="/goals", tags=["user-goals"])


@user_goals_router.post("/", status_code=status.HTTP_201_CREATED)
def create_goal(
    goal_data: UserGoalCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    try:
        return service.create_goal(current_user, goal_data)
    except UserGoalCreationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@user_goals_router.get(
    "/current",
    status_code=status.HTTP_200_OK,
)
def get_current_goal(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    goal = service.get_current_goal(current_user)
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active goal found for the user.",
        )
    return goal


@user_goals_router.get(
    "/history",
    status_code=status.HTTP_200_OK,
)
def get_goal_history(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum number of goals to return.")] = 100,
    offset: Annotated[int, Query(ge=0, description="Number of goals to skip.")] = 0,
) -> list[UserGoalPublic]:
    return service.get_goal_history(current_user, limit, offset)


@user_goals_router.get(
    "/{goal_id}",
    status_code=status.HTTP_200_OK,
)
def get_goal_by_id(
    goal_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    try:
        return service.get_goal_by_id(current_user, goal_id)
    except UserGoalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@user_goals_router.patch(
    "/{goal_id}",
    status_code=status.HTTP_200_OK,
)
def update_goal(
    goal_id: int,
    update_data: UserGoalUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    try:
        return service.update_goal(current_user, goal_id, update_data)
    except UserGoalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except UserGoalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@user_goals_router.post(
    "/{goal_id}/deactivate",
    status_code=status.HTTP_200_OK,
)
def deactivate_goal(
    goal_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    try:
        return service.deactivate_goal(current_user, goal_id)
    except UserGoalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@user_goals_router.post(
    "/{goal_id}/activate",
    status_code=status.HTTP_200_OK,
)
def activate_goal(
    goal_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    try:
        return service.activate_goal(current_user, goal_id)
    except UserGoalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
