"""Database row validation and mapping for progress photo."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from core.errors.repository import ProgressPhotoRowError
from data.validation import RowValidator
from schemas.progress_photo_schema import ProgressPhotoPublic

if TYPE_CHECKING:
    from datetime import date, datetime

_validator = RowValidator(ProgressPhotoRowError)


class ProgressPhotoRow(TypedDict):
    id: int
    user_id: int
    photo_url: str
    entry_date: date
    notes: str | None
    created_at: datetime


def _parse_progress_photo_row(row: dict[str, object]) -> ProgressPhotoRow:
    """Validate and normalize a raw database row into a typed ProgressPhotoRow."""

    id_value = _validator.require_int(row.get("id"), "id")
    user_id = _validator.require_int(row.get("user_id"), "user_id")
    photo_url = _validator.require_str(row.get("photo_url"), "photo_url")
    entry_date = _validator.require_date(row.get("entry_date"), "entry_date")
    notes = _validator.require_optional_str(row.get("notes"), "notes")
    created_at = _validator.require_datetime(row.get("created_at"), "created_at")

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
