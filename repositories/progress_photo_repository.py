"""
Progress Photo Repository

This module handles all database interactions for the ProgressPhoto entity.
It translates between database rows (now dicts) and Pydantic models.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Final, TypedDict

from core.errors.repository import ProgressPhotoRepositoryError, ProgressPhotoRowError
from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from data.queries import QUERIES
from schemas.progress_photo_schema import (
    ProgressPhotoCreate,
    ProgressPhotoPublic,
    ProgressPhotoUpdate,
)


class ProgressPhotoRow(TypedDict):
    id: int
    user_id: int
    photo_url: str
    entry_date: date
    notes: str | None
    created_at: datetime


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
        return self._row_to_progress_photo(row)

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
        return self._row_to_progress_photo(row)

    def list_by_user(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
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
        safe_limit = max(1, min(limit, 1000))
        safe_offset = max(0, offset)

        filters: list[str] = []
        params: list[object] = [user_id]

        if date_from is not None:
            filters.append(QUERIES.progress_photos.filter_date_from)
            params.append(date_from)

        if date_to is not None:
            filters.append(QUERIES.progress_photos.filter_date_to)
            params.append(date_to)

        sql = QUERIES.progress_photos.list_by_user.format(filters=" ".join(filters))
        params.extend([safe_limit, safe_offset])

        rows = fetch_all(sql, tuple(params))
        return [self._row_to_progress_photo(row) for row in rows]

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

    @staticmethod
    def _parse_progress_photo_row(row: dict[str, object]) -> ProgressPhotoRow:
        """Validate and normalize a raw database row into a typed ProgressPhotoRow."""
        id_value = row.get("id")
        user_id = row.get("user_id")
        photo_url = row.get("photo_url")
        entry_date = row.get("entry_date")
        notes = row.get("notes")
        created_at = row.get("created_at")

        if not isinstance(id_value, int):
            raise ProgressPhotoRowError.invalid_type("id", "int")
        if not isinstance(user_id, int):
            raise ProgressPhotoRowError.invalid_type("user_id", "int")
        if not isinstance(photo_url, str):
            raise ProgressPhotoRowError.invalid_type("photo_url", "str")
        if not isinstance(entry_date, date):
            raise ProgressPhotoRowError.invalid_type("entry_date", "date")
        if notes is not None and not isinstance(notes, str):
            raise ProgressPhotoRowError.invalid_type("notes", "str | None")
        if not isinstance(created_at, datetime):
            raise ProgressPhotoRowError.invalid_type("created_at", "datetime")

        return ProgressPhotoRow(
            id=id_value,
            user_id=user_id,
            photo_url=photo_url,
            entry_date=entry_date,
            notes=notes,
            created_at=created_at,
        )

    @classmethod
    def _row_to_progress_photo(cls, row: dict[str, object]) -> ProgressPhotoPublic:
        """Convert a raw database row into a validated ProgressPhotoPublic model."""
        progress_photo_row = cls._parse_progress_photo_row(row)
        return ProgressPhotoPublic.model_validate(progress_photo_row)
