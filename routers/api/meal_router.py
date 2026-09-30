from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from dependencies.auth import get_current_user
from dependencies.providers import get_meal_service
from schemas.meal_schema import MealCreate, MealPublic, MealUpdate
from schemas.user_schema import UserInternal
from services.meal_service import MealService
from utils.validators import validate_meal_type

meal_router = APIRouter(prefix="/meals", tags=["meals"])


@meal_router.post("/", status_code=status.HTTP_201_CREATED)
def create_meal(
    meal_data: MealCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealService, Depends(get_meal_service)],
) -> MealPublic:
    """
    Create a new meal for the authenticated user.
    """
    return service.create_meal(current_user.id, meal_data)


@meal_router.get("/{meal_id}", status_code=status.HTTP_200_OK)
def get_meal_by_id(
    meal_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealService, Depends(get_meal_service)],
) -> MealPublic:
    """
    Retrieve a meal by ID, ensuring it belongs to the user.
    """
    return service.get_visible_by_user(meal_id, current_user.id)


@meal_router.get("/", status_code=status.HTTP_200_OK)
def list_meals(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealService, Depends(get_meal_service)],
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum number of meals to return.")] = 100,
    offset: Annotated[int, Query(ge=0, description="Number of meals to skip.")] = 0,
    date_from: Annotated[date | None, Query(description="Filter meals from this date inclusive.")] = None,
    date_to: Annotated[date | None, Query(description="Filter meals up to this date inclusive.")] = None,
    meal_type: Annotated[str | None, Query(description="Filter by meal type.")] = None,
) -> list[MealPublic]:
    """
    List meals belonging to the authenticated user with optional filtering and pagination.
    """
    normalized_meal_type = _normalize_meal_type(meal_type)
    return service.list_visible_by_user(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        date_from=date_from,
        date_to=date_to,
        meal_type=normalized_meal_type,
    )


@meal_router.patch("/{meal_id}", status_code=status.HTTP_200_OK)
def update_meal(
    meal_id: int,
    meal_data: MealUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealService, Depends(get_meal_service)],
) -> MealPublic:
    """
    Update a meal by ID, ensuring it belongs to the user.
    """
    return service.update_meal(meal_id, current_user.id, meal_data)


@meal_router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal(
    meal_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealService, Depends(get_meal_service)],
) -> None:
    """
    Delete a meal by ID, ensuring it belongs to the user.
    """
    service.delete_meal(meal_id, current_user.id)


def _normalize_meal_type(meal_type: str | None) -> str | None:
    if meal_type is None:
        return None

    return validate_meal_type(meal_type)
