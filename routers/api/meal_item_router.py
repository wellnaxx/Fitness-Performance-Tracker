"""Authenticated item operations nested beneath an owned meal."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import RequestValidationError
from fastapi.params import Path

from dependencies.auth import get_current_user
from dependencies.providers import get_meal_item_service
from schemas.meal_item_schema import MealItemCreate, MealItemPublic, MealItemUpdate
from schemas.user_schema import UserInternal
from services.meal_item_service import MealItemService

meal_item_router = APIRouter(
    prefix="/meals/{meal_id}/meal_items",
    tags=["meal_items"],
    responses={
        401: {"description": "Missing, invalid, expired, or revoked Bearer access token."},
        404: {"description": "The meal is missing or unowned, or the item is absent from that meal."},
        500: {"description": "Persistence failure; internal details are excluded from the response."},
    },
)


@meal_item_router.post("/", status_code=status.HTTP_201_CREATED)
def create(
    meal_id: Annotated[int, Path(gt=0, description="Parent meal ID.")],
    meal_item_data: MealItemCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealItemService, Depends(get_meal_item_service)],
) -> MealItemPublic:
    """Create an item in a meal owned by the authenticated user.

    Args:
        meal_id: Positive parent meal ID from the path; must match the body's meal_id.
        meal_item_data: Item name (1..100 characters), nonnegative calories and
            macronutrients, optional nonnegative serving size, and matching meal_id.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected meal-item service.

    Returns:
        The persisted item, including its ID and creation timestamp (HTTP 201).

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for invalid IDs, invalid or missing body
            fields, or a body meal_id that differs from the path.
        MealNotFoundError: HTTP 404 if the parent meal is missing or unowned.
        MealItemCreationError: HTTP 500 if creation fails.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    if meal_item_data.meal_id != meal_id:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("body", "meal_id"),
                    "msg": "Value error, meal_id must match the path meal_id.",
                    "input": meal_item_data.meal_id,
                },
            ]
        )
    return service.create(current_user.id, meal_item_data)


@meal_item_router.get("/{meal_item_id}", status_code=status.HTTP_200_OK)
def get_by_id(
    meal_id: Annotated[int, Path(gt=0, description="Parent meal ID.")],
    meal_item_id: Annotated[int, Path(gt=0, description="Meal item ID within the parent meal.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealItemService, Depends(get_meal_item_service)],
) -> MealItemPublic:
    """Retrieve one item within an owned meal.

    Args:
        meal_id: Positive parent meal ID from the path.
        meal_item_id: Positive item ID from the path.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected meal-item service.

    Returns:
        The matching item with Decimal nutrition values serialized as strings (HTTP 200).

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for an invalid or nonpositive path ID.
        MealNotFoundError: HTTP 404 if the parent meal is missing or unowned.
        MealItemNotFoundError: HTTP 404 if the item is missing or belongs to another meal.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    return service.get_by_id(current_user.id, meal_id, meal_item_id)


@meal_item_router.get("/", status_code=status.HTTP_200_OK)
def list_by_meal(
    meal_id: Annotated[int, Path(gt=0, description="Parent meal ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealItemService, Depends(get_meal_item_service)],
) -> list[MealItemPublic]:
    """List all items in an owned meal in ascending ID order without pagination.

    Args:
        meal_id: Positive parent meal ID from the path.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected meal-item service.

    Returns:
        All matching items (HTTP 200), or [] for an owned meal without items.

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for an invalid or nonpositive meal ID.
        MealNotFoundError: HTTP 404 if the parent meal is missing or unowned.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    return service.list_by_meal(current_user.id, meal_id)


@meal_item_router.patch("/{meal_item_id}", status_code=status.HTTP_200_OK)
def update(
    meal_id: Annotated[int, Path(gt=0, description="Parent meal ID.")],
    meal_item_id: Annotated[int, Path(gt=0, description="Meal item ID within the parent meal.")],
    update_data: MealItemUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealItemService, Depends(get_meal_item_service)],
) -> MealItemPublic:
    """Partially update an item within an owned meal.

    Args:
        meal_id: Positive parent meal ID from the path.
        meal_item_id: Positive item ID from the path.
        update_data: Optional name, serving size, and nutrition changes. Omitted
            and null fields preserve stored values; zero values are applied.
            An empty object preserves current values. The parent meal cannot change.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected meal-item service.

    Returns:
        The persisted item, including unchanged fields and creation timestamp (HTTP 200).

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for invalid IDs or an invalid or missing JSON body.
        MealNotFoundError: HTTP 404 if the parent meal is missing or unowned.
        MealItemNotFoundError: HTTP 404 if the item is absent from the meal or disappears.
        MealItemUpdateError: HTTP 500 if the update fails.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    return service.update(current_user.id, meal_id, meal_item_id, update_data)


@meal_item_router.delete("/{meal_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    meal_id: Annotated[int, Path(gt=0, description="Parent meal ID.")],
    meal_item_id: Annotated[int, Path(gt=0, description="Meal item ID within the parent meal.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealItemService, Depends(get_meal_item_service)],
) -> None:
    """Delete one item within an owned meal.

    Args:
        meal_id: Positive parent meal ID from the path.
        meal_item_id: Positive item ID from the path.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected meal-item service.

    Returns:
        An empty response after deletion (HTTP 204).

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for an invalid or nonpositive path ID.
        MealNotFoundError: HTTP 404 if the parent meal is missing or unowned.
        MealItemNotFoundError: HTTP 404 if the item is absent from the meal or disappears.
        MealItemDeleteError: HTTP 500 if deletion fails.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    service.delete(current_user.id, meal_id, meal_item_id)
