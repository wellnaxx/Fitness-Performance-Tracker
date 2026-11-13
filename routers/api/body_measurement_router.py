"""Authenticated endpoints for body measurement histories and individual entries."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.params import Path, Query

from dependencies.auth import get_current_user
from dependencies.pagination import get_pagination
from dependencies.providers import get_body_measurement_service
from schemas.body_measurement_schema import BodyMeasurementCreate, BodyMeasurementPublic, BodyMeasurementUpdate
from schemas.user_schema import UserInternal
from services.body_measurement_service import BodyMeasurementService
from utils.pagination import PaginationParams

body_measurement_router = APIRouter(
    prefix="/body_measurements",
    tags=["body_measurements"],
    responses={
        401: {"description": "Missing, invalid, expired, or revoked Bearer access token."},
        500: {"description": "Persistence failure; internal details are excluded from the response."},
    },
)


@body_measurement_router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "An entry already exists for this user and date."}},
)
def create_body_measurement_entry(
    body_measurement_data: BodyMeasurementCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[BodyMeasurementService, Depends(get_body_measurement_service)],
) -> BodyMeasurementPublic:
    """Create a measurement entry for the authenticated user.

    Args:
        body_measurement_data: Measurement date and at least one positive circumference in centimeters.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected body measurement service.

    Returns:
        The persisted entry with its ID and timestamps (HTTP 201).

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for an invalid or missing JSON body.
        BodyMeasurementDateConflictError: HTTP 409 if this user already has an entry on the date,
            including a concurrent write after the initial availability check.
        BodyMeasurementCreationError: HTTP 500 if creation fails.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    return service.create(current_user.id, body_measurement_data)


@body_measurement_router.get("/", status_code=status.HTTP_200_OK)
def list_body_measurement_entries(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[BodyMeasurementService, Depends(get_body_measurement_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    date_from: Annotated[date | None, Query(description="Inclusive earliest entry date (YYYY-MM-DD).")] = None,
    date_to: Annotated[date | None, Query(description="Inclusive latest entry date (YYYY-MM-DD).")] = None,
) -> list[BodyMeasurementPublic]:
    """List the authenticated user's entries in descending entry-date and ID order.

    Args:
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected body measurement service.
        pagination: Shared limit/offset query parameters; defaults are 100/0.
            Limit must be 1..1000 and offset must be nonnegative.
        date_from: Optional inclusive lower date bound.
        date_to: Optional inclusive upper date bound.

    Returns:
        A page of owned entries (HTTP 200). Empty histories, exhausted pages,
        and reversed date bounds return [].

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for invalid pagination or date query parameters.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    return service.list_by_user(
        user_id=current_user.id,
        limit=pagination.limit,
        offset=pagination.offset,
        date_from=date_from,
        date_to=date_to,
    )


@body_measurement_router.get(
    "/latest",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "The authenticated user has no body measurement entries."}},
)
def get_latest_body_measurement_entry(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[BodyMeasurementService, Depends(get_body_measurement_service)],
) -> BodyMeasurementPublic:
    """Retrieve the user's latest entry by entry date, then ID.

    Args:
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected body measurement service.

    Returns:
        The most recent owned entry (HTTP 200).

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        BodyMeasurementNotFoundError: HTTP 404 if this user's history is empty.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    return service.get_latest(current_user.id)


@body_measurement_router.get(
    "/date/{entry_date}",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "No owned entry matches the requested date."}},
)
def get_body_measurement_entry_by_date(
    entry_date: Annotated[date, Path(description="Exact measurement date (YYYY-MM-DD).")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[BodyMeasurementService, Depends(get_body_measurement_service)],
) -> BodyMeasurementPublic:
    """Retrieve the authenticated user's entry for an exact date.

    Args:
        entry_date: Measurement date from the path.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected body measurement service.

    Returns:
        The matching owned entry (HTTP 200).

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for an invalid date path parameter.
        BodyMeasurementNotFoundError: HTTP 404 if this user has no entry on the date.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    return service.get_by_date(current_user.id, entry_date)


@body_measurement_router.get(
    "/{entry_id}",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "The entry is missing or belongs to another user."}},
)
def get_body_measurement_entry_by_id(
    entry_id: Annotated[int, Path(gt=0, description="Body measurement entry ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[BodyMeasurementService, Depends(get_body_measurement_service)],
) -> BodyMeasurementPublic:
    """Retrieve one body measurement entry belonging to the authenticated user.

    Args:
        entry_id: Positive entry ID from the path.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected body measurement service.

    Returns:
        The matching owned entry (HTTP 200).

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for a nonpositive or invalid entry ID.
        BodyMeasurementNotFoundError: HTTP 404 if the entry is missing or unowned.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    return service.get_by_id(current_user.id, entry_id)


@body_measurement_router.patch(
    "/{entry_id}",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "The entry is missing or belongs to another user."},
        409: {"description": "Another entry for this user already occupies the requested date."},
    },
)
def update_body_measurement_entry(
    entry_id: Annotated[int, Path(gt=0, description="Body measurement entry ID.")],
    update_data: BodyMeasurementUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[BodyMeasurementService, Depends(get_body_measurement_service)],
) -> BodyMeasurementPublic:
    """Partially update an owned entry, optionally changing its measurement date.

    Args:
        entry_id: Positive entry ID from the path.
        update_data: Fields to change. Omitted and null fields keep their stored values;
            an empty object is valid. Measurements must be positive. Empty notes are valid,
            but null does not clear notes or measurements. Keeping the same date is valid.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected body measurement service.

    Returns:
        The resulting entry, or its current values for an empty update (HTTP 200).

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for an invalid entry ID or JSON body.
        BodyMeasurementNotFoundError: HTTP 404 if the entry is missing or unowned.
        BodyMeasurementDateConflictError: HTTP 409 if another owned entry occupies the new date.
        BodyMeasurementUpdateError: HTTP 500 if the update fails.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    return service.update(current_user.id, entry_id, update_data)


@body_measurement_router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "The entry is missing or belongs to another user."}},
)
def delete_body_measurement_entry(
    entry_id: Annotated[int, Path(gt=0, description="Body measurement entry ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[BodyMeasurementService, Depends(get_body_measurement_service)],
) -> None:
    """Delete an owned body measurement entry.

    Args:
        entry_id: Positive entry ID from the path.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected body measurement service.

    Returns:
        An empty response body after successful deletion (HTTP 204).

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for a nonpositive or invalid entry ID.
        BodyMeasurementNotFoundError: HTTP 404 if missing or unowned, including repeated deletion.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    service.delete(current_user.id, entry_id)
