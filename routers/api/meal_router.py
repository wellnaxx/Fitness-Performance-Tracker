from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.errors.meal import MealCreationError, MealDeleteError, MealNotFoundError, MealUpdateError
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
    try:
        return service.create_meal(current_user.id, meal_data)
    except MealCreationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@meal_router.get("/{meal_id}", status_code=status.HTTP_200_OK)
def get_meal_by_id(
    meal_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealService, Depends(get_meal_service)],
) -> MealPublic:
    """
    Retrieve a meal by ID, ensuring it belongs to the user.
    """
    try:
        return service.get_visible_by_user(meal_id, current_user.id)
    except MealNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


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
    try:
        return service.update_meal(meal_id, current_user.id, meal_data)
    except MealNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except MealUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@meal_router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal(
    meal_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealService, Depends(get_meal_service)],
) -> None:
    """
    Delete a meal by ID, ensuring it belongs to the user.
    """
    try:
        service.delete_meal(meal_id, current_user.id)
    except MealNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except MealDeleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


def _normalize_meal_type(meal_type: str | None) -> str | None:
    if meal_type is None:
        return None

    try:
        return validate_meal_type(meal_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
