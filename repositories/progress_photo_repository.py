"""
Progress Photo Repository

This module handles all database interactions for the ProgressPhoto entity.
It delegates database row validation and conversion to the dedicated mapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from core.errors.repository import ProgressPhotoRepositoryError
from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from data.mappers.progress_photo import map_progress_photo
from data.queries import QUERIES
from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET, normalize_pagination

if TYPE_CHECKING:
    from datetime import date

    from schemas.progress_photo_schema import (
        ProgressPhotoCreate,
        ProgressPhotoPublic,
        ProgressPhotoUpdate,
    )


class ProgressPhotoRepository:
    """
    Repository for ProgressPhoto database operations.

    Responsibilities:
    - Execute SQL queries related to progress photos
    - Convert database row dicts to ProgressPhotoPublic models
    - Handle all progress-photo-related database logic
    """

    _PROGRESS_PHOTO_UPDATE_WHITELIST: Final[set[str]] = {
        "photo_url",
        "entry_date",
        "notes",
    }

    def create(
        self,
        user_id: int,
        photo_data: ProgressPhotoCreate,
    ) -> ProgressPhotoPublic:
        """
        Create a new progress photo entry for a user.

        Args:
            user_id: Owner user ID.
            photo_data: Progress photo creation payload.

        Returns:
            The newly created progress photo.

        Raises:
            ProgressPhotoRepositoryError: If the inserted row cannot be retrieved afterwards.
        """
        photo_id = execute_insert(
            QUERIES.progress_photos.create,
            (user_id, str(photo_data.photo_url), photo_data.entry_date, photo_data.notes),
        )

        photo = self.get_by_id(photo_id)
        if photo is None:
            raise ProgressPhotoRepositoryError.inserted_missing(photo_id)
        return photo

    def get_by_id(self, photo_id: int) -> ProgressPhotoPublic | None:
        """
        Retrieve a progress photo by its database ID.

        Args:
            photo_id: Photo ID.

        Returns:
            The progress photo if found, otherwise None.
        """
        row = fetch_one(QUERIES.progress_photos.get_by_id, (photo_id,))
        if row is None:
            return None
        return map_progress_photo(row)

    def get_by_user_and_id(
        self,
        user_id: int,
        photo_id: int,
    ) -> ProgressPhotoPublic | None:
        """
        Retrieve a progress photo by ID only if it belongs to the user.

        Args:
            user_id: Owner user ID.
            photo_id: Photo ID.

        Returns:
            The photo if found and owned by the user, otherwise None.
        """
        row = fetch_one(
            QUERIES.progress_photos.get_by_user_and_id,
            (user_id, photo_id),
        )
        if row is None:
            return None
        return map_progress_photo(row)

    def list_by_user(
        self,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ProgressPhotoPublic]:
        """
        List progress photos for a user with pagination and date filters.

        Args:
            user_id: Owner user ID.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip.
            date_from: Optional inclusive lower bound for `entry_date`.
            date_to: Optional inclusive upper bound for `entry_date`.

        Returns:
            Progress photos ordered from newest to oldest.
        """
        pagination = normalize_pagination(limit, offset)

        filters: list[str] = []
        params: list[object] = [user_id]

        if date_from is not None:
            filters.append(QUERIES.progress_photos.filter_date_from)
            params.append(date_from)

        if date_to is not None:
            filters.append(QUERIES.progress_photos.filter_date_to)
            params.append(date_to)

        sql = QUERIES.progress_photos.list_by_user.format(filters=" ".join(filters))
        params.extend([pagination.limit, pagination.offset])

        rows = fetch_all(sql, tuple(params))
        return [map_progress_photo(row) for row in rows]

    def update_owned(
        self,
        user_id: int,
        photo_id: int,
        update_data: ProgressPhotoUpdate,
    ) -> ProgressPhotoPublic | None:
        """
        Partially update a progress photo owned by the user.

        Args:
            user_id: Owner user ID.
            photo_id: Photo ID.
            update_data: Partial update payload.

        Returns:
            The updated progress photo if found, otherwise None.

        Raises:
            ProgressPhotoRepositoryError: If any provided fields are not allowed to be updated.
        """
        fields = update_data.model_dump(exclude_none=True)
        if not fields:
            return self.get_by_user_and_id(user_id, photo_id)

        if "photo_url" in fields:
            fields["photo_url"] = str(fields["photo_url"])

        unknown = set(fields) - self._PROGRESS_PHOTO_UPDATE_WHITELIST
        if unknown:
            raise ProgressPhotoRepositoryError.invalid_update_fields(unknown)

        set_clause = ", ".join(f"{field} = %s" for field in fields)
        sql = QUERIES.progress_photos.update_owned.format(set_clause=set_clause)
        execute_write(sql, (*fields.values(), user_id, photo_id))
        return self.get_by_user_and_id(user_id, photo_id)

    def delete_owned(self, user_id: int, photo_id: int) -> bool:
        """
        Delete a progress photo owned by the user.

        Args:
            user_id: Owner user ID.
            photo_id: Photo ID.

        Returns:
            True if a row was deleted, otherwise False.
        """
        return (
            execute_write(
                QUERIES.progress_photos.delete_owned,
                (user_id, photo_id),
            )
            > 0
        )
