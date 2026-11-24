from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.params import Path

from dependencies.auth import get_current_user
from dependencies.pagination import get_pagination
from dependencies.providers import get_progress_photo_service
from schemas.progress_photo_schema import ProgressPhotoCreate, ProgressPhotoPublic, ProgressPhotoUpdate
from schemas.user_schema import UserInternal
from services.progress_photo_service import ProgressPhotoService
from utils.pagination import PaginationParams

progress_photo_router = APIRouter(
    prefix="/progress_photos",
    tags=["progress_photos"],
    responses={
        401: {"description": "Missing, invalid, expired, or revoked Bearer access token."},
        500: {"description": "Persistence failure; internal details are excluded from the response."},
    },
)


@progress_photo_router.post("/", status_code=status.HTTP_201_CREATED)
def create(
    photo_data: ProgressPhotoCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[ProgressPhotoService, Depends(get_progress_photo_service)],
) -> ProgressPhotoPublic:
    """Create a progress photo record for the authenticated user.

    Args:
        photo_data: HTTP(S) photo URL, entry date, and optional notes up to 1000 characters.
            Multiple records may share a date or URL. This endpoint stores a reference
            to an image; it does not upload files or check URL availability.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected progress-photo service.

    Returns:
        The persisted record with its ID, owner, and creation timestamp (HTTP 201).

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for an invalid or missing JSON body.
        ProgressPhotoCreationError: HTTP 500 if creation fails.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    return service.create(current_user.id, photo_data)


@progress_photo_router.get(
    "/{photo_id}",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "The record is missing or belongs to another user."}},
)
def get_by_id(
    photo_id: Annotated[int, Path(gt=0, description="Progress photo record ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[ProgressPhotoService, Depends(get_progress_photo_service)],
) -> ProgressPhotoPublic:
    """Retrieve one progress photo record belonging to the authenticated user.

    Args:
        photo_id: Positive record ID from the path.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected progress-photo service.

    Returns:
        The owned URL record and its metadata (HTTP 200); no image bytes are downloaded.

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for an invalid or nonpositive photo ID.
        ProgressPhotoNotFoundError: HTTP 404 if the record is missing or unowned.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    return service.get_by_id(current_user.id, photo_id)


@progress_photo_router.get("/", status_code=status.HTTP_200_OK)
def list_by_user(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[ProgressPhotoService, Depends(get_progress_photo_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    date_from: Annotated[
        date | None,
        Query(description="Inclusive earliest entry date (YYYY-MM-DD)."),
    ] = None,
    date_to: Annotated[
        date | None,
        Query(description="Inclusive latest entry date (YYYY-MM-DD)."),
    ] = None,
) -> list[ProgressPhotoPublic]:
    """List the user's photo records in descending entry-date and ID order.

    Args:
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected progress-photo service.
        pagination: Shared limit/offset parameters; defaults are 100/0.
            Limit must be 1..1000 and offset must be nonnegative.
        date_from: Optional inclusive lower entry-date bound.
        date_to: Optional inclusive upper entry-date bound.

    Returns:
        A page of owned records (HTTP 200). Empty histories, exhausted pages,
        and reversed date bounds return []. Records on the same date are ordered by descending ID.

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


@progress_photo_router.patch(
    "/{photo_id}",
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "The record is missing, unowned, or disappeared during the update."}},
)
def update(
    photo_id: Annotated[int, Path(gt=0, description="Progress photo record ID.")],
    update_data: ProgressPhotoUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[ProgressPhotoService, Depends(get_progress_photo_service)],
) -> ProgressPhotoPublic:
    """Partially update an owned progress photo record.

    Args:
        photo_id: Positive record ID from the path.
        update_data: Optional URL, date, and notes changes. Omitted and null fields
            preserve stored values; an empty object is allowed. Notes may be set to an
            empty string. Updating the URL does not replace or delete an image file.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected progress-photo service.

    Returns:
        The resulting record, preserving its ID, owner, and creation timestamp (HTTP 200).

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for an invalid ID or an invalid or missing JSON body.
        ProgressPhotoNotFoundError: HTTP 404 if the record is missing, unowned, or disappears.
        ProgressPhotoUpdateError: HTTP 500 if the update fails.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    return service.update(current_user.id, photo_id, update_data)


@progress_photo_router.delete(
    "/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "The record is missing, unowned, or disappeared before deletion."}},
)
def delete(
    photo_id: Annotated[int, Path(gt=0, description="Progress photo record ID.")],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[ProgressPhotoService, Depends(get_progress_photo_service)],
) -> None:
    """Delete an owned progress photo record while leaving the image file unaffected.

    Args:
        photo_id: Positive record ID from the path.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected progress-photo service.

    Returns:
        An empty response after deleting the record (HTTP 204).

    Raises:
        HTTPException: HTTP 401 if authentication fails.
        RequestValidationError: HTTP 422 for an invalid or nonpositive photo ID.
        ProgressPhotoNotFoundError: HTTP 404 if the record is missing, unowned, or disappears.
        ProgressPhotoDeleteError: HTTP 500 if deletion fails.
        DatabaseError: HTTP 500 with a safe message if persistence fails.
    """
    service.delete(current_user.id, photo_id)


"""Authenticated CRUD endpoints for progress photo URLs and metadata."""
