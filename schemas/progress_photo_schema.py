from __future__ import annotations

from datetime import date, datetime

from pydantic import AnyHttpUrl, BaseModel, Field


class ProgressPhotoBase(BaseModel):
    """Base schema for progress photo entries."""

    photo_url: AnyHttpUrl = Field(
        description="Publicly accessible URL of the progress photo",
    )
    entry_date: date = Field(
        description="Date of the progress photo entry",
        examples=["2024-01-01"],
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Additional notes about the progress photo entry",
    )


class ProgressPhotoCreate(ProgressPhotoBase):
    """Schema for creating a new progress photo entry."""


class ProgressPhotoUpdate(BaseModel):
    """Schema for updating an existing progress photo entry. All fields are optional."""

    photo_url: AnyHttpUrl | None = Field(
        default=None,
        description="Publicly accessible URL of the progress photo",
    )
    entry_date: date | None = Field(
        default=None,
        description="Date of the progress photo entry",
        examples=["2024-01-01"],
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Additional notes about the progress photo entry",
    )


class ProgressPhotoPublic(ProgressPhotoBase):
    """Schema for returning progress photo entry data to clients."""

    id: int
    user_id: int
    created_at: datetime
