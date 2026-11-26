"""Persistence contract for user-owned progress photo URLs and metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET

if TYPE_CHECKING:
    from datetime import date

    from schemas.progress_photo_schema import ProgressPhotoCreate, ProgressPhotoPublic, ProgressPhotoUpdate


class ProgressPhotoRepositoryPort(Protocol):
    """Store and retrieve progress photo records with user-scoped operations.

    Implementations persist photo URLs and metadata, rather than image files.
    Database, row-validation, and repository errors propagate on persistence
    failures. Missing or unowned records return None or False as documented;
    services decide whether to raise a not-found error.
    """

    def create(self, user_id: int, photo_data: ProgressPhotoCreate) -> ProgressPhotoPublic:
        """Create a new progress photo entry for a user.

        Args:
            user_id: Owner user ID.
            photo_data: Progress photo creation payload.

        Returns:
            The newly created progress photo.

        Raises:
            ProgressPhotoRepositoryError: If the inserted row cannot be retrieved afterwards.
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def get_by_id(self, photo_id: int) -> ProgressPhotoPublic | None:
        """Retrieve a progress photo by its database ID.

        Args:
            photo_id: Photo ID.

        Returns:
            The progress photo if found, otherwise None.

        This lookup does not authorize access; services must verify ownership or visibility.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def get_by_user_and_id(self, user_id: int, photo_id: int) -> ProgressPhotoPublic | None:
        """Retrieve a progress photo by ID only if it belongs to the user.

        Args:
            user_id: Owner user ID.
            photo_id: Photo ID.

        Returns:
            The photo if found and owned by the user, otherwise None.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def list_by_user(
        self,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ProgressPhotoPublic]:
        """List progress photos for a user with pagination and date filters.

        Args:
            user_id: Owner user ID.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip.
            date_from: Optional inclusive lower bound for `entry_date`.
            date_to: Optional inclusive upper bound for `entry_date`.

        Returns:
            Progress photos ordered from newest to oldest.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def update_owned(
        self,
        user_id: int,
        photo_id: int,
        update_data: ProgressPhotoUpdate,
    ) -> ProgressPhotoPublic | None:
        """Partially update a progress photo owned by the user.

        Args:
            user_id: Owner user ID.
            photo_id: Photo ID.
            update_data: URL, date, or notes changes. Omitted and None-valued fields
                preserve stored values; notes cannot be cleared with None.

        Returns:
            The updated record, current values for an empty update, or None if missing or unowned.

        Raises:
            ProgressPhotoRepositoryError: If any provided fields are not allowed to be updated.
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def delete_owned(self, user_id: int, photo_id: int) -> bool:
        """Delete a progress photo owned by the user.

        Args:
            user_id: Owner user ID.
            photo_id: Photo ID.

        Returns:
            True if the record was deleted; False if missing or owned by another user.
            The image at the stored URL is unaffected.

        Raises:
            DatabaseError: If the database operation fails.
        """
        ...
