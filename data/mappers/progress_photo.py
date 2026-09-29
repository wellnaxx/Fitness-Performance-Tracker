"""Database row validation and mapping for progress photo."""

from __future__ import annotations

from datetime import date, datetime
from typing import TypedDict

from core.errors.repository import ProgressPhotoRowError
from schemas.progress_photo_schema import ProgressPhotoPublic


class ProgressPhotoRow(TypedDict):
    id: int
    user_id: int
    photo_url: str
    entry_date: date
    notes: str | None
    created_at: datetime


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


def map_progress_photo(row: dict[str, object]) -> ProgressPhotoPublic:
    """Convert a raw database row into a validated ProgressPhotoPublic model."""
    progress_photo_row = _parse_progress_photo_row(row)
    return ProgressPhotoPublic.model_validate(progress_photo_row)
