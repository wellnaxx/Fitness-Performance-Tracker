"""HTTP endpoints for meal operations."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.params import Path

from dependencies.auth import get_current_user
from dependencies.pagination import get_pagination
from dependencies.providers import get_meal_service
from schemas.meal_schema import MealCreate, MealPublic, MealUpdate
from schemas.user_schema import UserInternal
from services.meal_service import MealService
from utils.pagination import PaginationParams
from utils.validators import validate_meal_type

meal_router = APIRouter(
    prefix="/meals",
    tags=["meals"],
    responses={
        500: {"description": "Persistence failure; internal details are excluded from the response."},
        401: {"description": "Missing, invalid, expired, or revoked Bearer access token."},
    },
)


@meal_router.post("/", status_code=status.HTTP_201_CREATED)
def create_meal(
    meal_data: MealCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealService, Depends(get_meal_service)],
) -> MealPublic:
    """Create a new meal for the authenticated user.

    Args:
        meal_data: Validated meal creation or partial-update values.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The persisted record with its assigned ID (HTTP 201).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        MealCreationError: HTTP 500. If creation fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.create(current_user.id, meal_data)


@meal_router.get(
    "/{meal_id}",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "If the record is missing or unowned."}},
)
def get_meal_by_id(
    meal_id: Annotated[int, Path(gt=0, description="Meal ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealService, Depends(get_meal_service)],
) -> MealPublic:
    """Retrieve a meal by ID, ensuring it belongs to the user.

    Args:
        meal_id: Positive meal ID.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        MealNotFoundError: HTTP 404. If the record is missing or unowned.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.get_by_id(current_user.id, meal_id)


@meal_router.get("/", status_code=status.HTTP_200_OK)
def list_meals(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealService, Depends(get_meal_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    date_from: Annotated[date | None, Query(description="Filter meals from this date inclusive.")] = None,
    date_to: Annotated[date | None, Query(description="Filter meals up to this date inclusive.")] = None,
    meal_type: Annotated[str | None, Query(description="Filter by meal type.")] = None,
) -> list[MealPublic]:
    """List meals belonging to the authenticated user with optional filtering and pagination.

    Args:
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.
        pagination: Shared limit/offset parameters: defaults 100/0, limit 1..1000, offset nonnegative.
        date_from: Optional inclusive lower date bound.
        date_to: Optional inclusive upper date bound.
        meal_type: Optional meal-type filter; normalized before the service call.

    Returns:
        Matching records in repository order, or [] when none match (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    normalized_meal_type = _normalize_meal_type(meal_type)
    return service.list_by_user(
        user_id=current_user.id,
        limit=pagination.limit,
        offset=pagination.offset,
        date_from=date_from,
        date_to=date_to,
        meal_type=normalized_meal_type,
    )


@meal_router.patch(
    "/{meal_id}",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "If the record is missing or unowned."}},
)
def update_meal(
    meal_id: Annotated[int, Path(gt=0, description="Meal ID.")],
    meal_data: MealUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealService, Depends(get_meal_service)],
) -> MealPublic:
    """Update a meal by ID, ensuring it belongs to the user.

    Args:
        meal_id: Positive meal ID.
        meal_data: Validated meal creation or partial-update values.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        MealNotFoundError: HTTP 404. If the record is missing or unowned.
        MealUpdateError: HTTP 500. If persistence fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.update(current_user.id, meal_id, meal_data)


@meal_router.delete(
    "/{meal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "If the record is missing or unowned."}},
)
def delete_meal(
    meal_id: Annotated[int, Path(gt=0, description="Meal ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[MealService, Depends(get_meal_service)],
) -> None:
    """Delete a meal by ID, ensuring it belongs to the user.

    Args:
        meal_id: Positive meal ID.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        An empty response after successful completion (HTTP 204).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        MealNotFoundError: HTTP 404. If the record is missing or unowned.
        MealDeleteError: HTTP 500. If persistence fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    service.delete(current_user.id, meal_id)


def _normalize_meal_type(meal_type: str | None) -> str | None:
    if meal_type is None:
        return None

    return validate_meal_type(meal_type)
