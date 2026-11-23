"""User-owned progress photo records containing URLs and metadata."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.errors.progress_photo import (
    ProgressPhotoCreationError,
    ProgressPhotoDeleteError,
    ProgressPhotoNotFoundError,
    ProgressPhotoUpdateError,
)
from core.errors.repository import ProgressPhotoRepositoryError
from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET

if TYPE_CHECKING:
    from datetime import date

    from ports.repositories.progress_photo_repository import ProgressPhotoRepositoryPort
    from schemas.progress_photo_schema import ProgressPhotoCreate, ProgressPhotoPublic, ProgressPhotoUpdate


class ProgressPhotoService:
    """Authorize existing records through user-scoped repository operations.

    Callers supply the authenticated user ID and schema-validated payloads. Multiple
    records may share a date or URL. The service stores references to images; it
    does not upload, download, check availability, or delete the image files.
    """

    def __init__(self, progress_photo_repository: ProgressPhotoRepositoryPort) -> None:
        """Initialize the service with its persistence contract.

        Args:
            progress_photo_repository: Repository for user-scoped photo records.
        """
        self.progress_photo_repo = progress_photo_repository
        self.logger = logging.getLogger(__name__)

    def create(self, user_id: int, photo_data: ProgressPhotoCreate) -> ProgressPhotoPublic:
        """Create a progress photo record for the authenticated user.

        Args:
            user_id: Authenticated owner user ID.
            photo_data: Validated HTTP(S) URL, entry date, and optional notes up to
                1000 characters. Repeated URLs and dates are allowed.

        Returns:
            The persisted record with its ID, owner, and creation timestamp.

        Raises:
            ProgressPhotoCreationError: If the repository reports a creation failure.
            DatabaseError: If the database operation fails.
            ProgressPhotoRowError: If readback contains invalid row types.
            ValidationError: If readback violates the public schema.
        """
        try:
            photo = self.progress_photo_repo.create(user_id, photo_data)
        except ProgressPhotoRepositoryError as exc:
            self.logger.exception("Progress photo creation failed | user_id=%s", user_id)
            raise ProgressPhotoCreationError.create_failed() from exc

        self.logger.info("Progress photo created | user_id=%s photo_id=%s", user_id, photo.id)
        return photo

    def get_by_id(self, user_id: int, photo_id: int) -> ProgressPhotoPublic:
        """Retrieve one progress photo record belonging to the user.

        Args:
            user_id: Authenticated owner user ID.
            photo_id: Requested progress photo record ID.

        Returns:
            The owned record, including its stored URL and metadata.

        Raises:
            ProgressPhotoNotFoundError: If the record is missing or owned by another user.
            ProgressPhotoRepositoryError: If the repository reports a lookup failure.
            DatabaseError: If the lookup fails.
            ProgressPhotoRowError: If the stored row has invalid types.
            ValidationError: If the stored row violates the public schema.
        """
        photo = self.progress_photo_repo.get_by_user_and_id(user_id, photo_id)
        if photo is None:
            self.logger.warning("Progress photo not found | user_id=%s photo_id=%s", user_id, photo_id)
            raise ProgressPhotoNotFoundError.not_found(photo_id)

        self.logger.debug("Progress photo retrieved | user_id=%s photo_id=%s", user_id, photo_id)
        return photo

    def list_by_user(
        self,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ProgressPhotoPublic]:
        """List the user's records in descending entry-date and ID order.

        Args:
            user_id: Authenticated owner user ID.
            limit: Maximum records; the repository applies shared pagination bounds.
            offset: Records to skip; the repository clamps negative values to zero.
            date_from: Optional inclusive lower entry-date bound.
            date_to: Optional inclusive upper entry-date bound.

        Returns:
            Matching records, or [] for an empty history, exhausted page, or reversed date range.

        Raises:
            ProgressPhotoRepositoryError: If the repository reports a listing failure.
            DatabaseError: If the listing fails.
            ProgressPhotoRowError: If a returned row has invalid types.
            ValidationError: If a returned row violates the public schema.
        """
        photos = self.progress_photo_repo.list_by_user(user_id, limit, offset, date_from, date_to)
        self.logger.debug(
            "Progress photos listed | user_id=%s count=%s limit=%s offset=%s",
            user_id,
            len(photos),
            limit,
            offset,
        )
        return photos

    def update(self, user_id: int, photo_id: int, update_data: ProgressPhotoUpdate) -> ProgressPhotoPublic:
        """Partially update an existing record after verifying ownership.

        Args:
            user_id: Authenticated owner user ID.
            photo_id: Record to update.
            update_data: Validated URL, date, or notes changes. Omitted and None-valued
                fields preserve stored values. Notes may be set to an empty string,
                but cannot be cleared to database NULL through this operation.

        Returns:
            The updated record, or current values for an empty or all-None update.
            Its ID, owner, and creation timestamp are preserved.

        Raises:
            ProgressPhotoNotFoundError: If missing, unowned, or disappearing during persistence.
            ProgressPhotoUpdateError: If the repository reports an update failure.
            ProgressPhotoRepositoryError: If the initial ownership lookup fails at the repository level.
            DatabaseError: If the lookup or update fails.
            ProgressPhotoRowError: If a returned row has invalid types.
            ValidationError: If a returned row violates the public schema.
        """
        existing_photo = self.progress_photo_repo.get_by_user_and_id(user_id, photo_id)
        if existing_photo is None:
            self.logger.warning(
                "Progress photo not found during update | user_id=%s photo_id=%s", user_id, photo_id
            )
            raise ProgressPhotoNotFoundError.not_found(photo_id)

        try:
            updated_photo = self.progress_photo_repo.update_owned(user_id, photo_id, update_data)
        except ProgressPhotoRepositoryError as exc:
            self.logger.exception("Progress photo update failed | user_id=%s photo_id=%s", user_id, photo_id)
            raise ProgressPhotoUpdateError.update_failed(photo_id) from exc

        if updated_photo is None:
            self.logger.warning(
                "Progress photo missing after update | user_id=%s photo_id=%s", user_id, photo_id
            )
            raise ProgressPhotoNotFoundError.not_accessible(photo_id)

        self.logger.info("Progress photo updated | user_id=%s photo_id=%s", user_id, photo_id)
        return updated_photo

    def delete(self, user_id: int, photo_id: int) -> None:
        """Delete an owned progress photo record after verifying its existence.

        Args:
            user_id: Authenticated owner user ID.
            photo_id: Record to delete. The image at its URL is unaffected.

        Returns:
            None after successful deletion.

        Raises:
            ProgressPhotoNotFoundError: If missing, unowned, or deleted after the ownership check.
            ProgressPhotoDeleteError: If the repository reports a deletion failure.
            ProgressPhotoRepositoryError: If the initial ownership lookup fails at the repository level.
            DatabaseError: If the lookup or deletion fails.
            ProgressPhotoRowError: If the ownership lookup returns invalid row types.
            ValidationError: If the ownership lookup violates the public schema.
        """
        existing_photo = self.progress_photo_repo.get_by_user_and_id(user_id, photo_id)
        if existing_photo is None:
            self.logger.warning(
                "Progress photo not found during deletion | user_id=%s photo_id=%s", user_id, photo_id
            )
            raise ProgressPhotoNotFoundError.not_found(photo_id)

        try:
            deleted_photo = self.progress_photo_repo.delete_owned(user_id, photo_id)
        except ProgressPhotoRepositoryError as exc:
            self.logger.exception("Progress photo deletion failed | user_id=%s photo_id=%s", user_id, photo_id)
            raise ProgressPhotoDeleteError.delete_failed(photo_id) from exc

        if not deleted_photo:
            self.logger.warning(
                "Progress photo deletion affected no row | user_id=%s photo_id=%s", user_id, photo_id
            )
            raise ProgressPhotoNotFoundError.not_accessible(photo_id)

        self.logger.info("Progress photo deleted | user_id=%s photo_id=%s", user_id, photo_id)
