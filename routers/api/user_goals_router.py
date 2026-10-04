from typing import Annotated

from fastapi import APIRouter, Depends, status

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

user_goals_router = APIRouter(prefix="/goals", tags=["user-goals"])


@user_goals_router.post("/", status_code=status.HTTP_201_CREATED)
def create_goal(
    goal_data: UserGoalCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    return service.create_goal(current_user, goal_data)


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
    return service.get_goal_history(current_user, pagination.limit, pagination.offset)


@user_goals_router.get(
    "/{goal_id}",
    status_code=status.HTTP_200_OK,
)
def get_goal_by_id(
    goal_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    return service.get_goal_by_id(current_user, goal_id)


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
    return service.update_goal(current_user, goal_id, update_data)


@user_goals_router.post(
    "/{goal_id}/deactivate",
    status_code=status.HTTP_200_OK,
)
def deactivate_goal(
    goal_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    return service.deactivate_goal(current_user, goal_id)


@user_goals_router.post(
    "/{goal_id}/activate",
    status_code=status.HTTP_200_OK,
)
def activate_goal(
    goal_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserGoalsService, Depends(get_user_goals_service)],
) -> UserGoalPublic:
    return service.activate_goal(current_user, goal_id)
