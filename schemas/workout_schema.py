from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class WorkoutBase(BaseModel):
    """Base workout model with common fields."""

    name: str = Field(
        min_length=1,
        max_length=100,
        description="Name of the workout",
        examples=["Full Body Strength", "Upper Body Hypertrophy"],
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional description of the workout",
        examples=["A comprehensive workout targeting all major muscle groups."],
    )
    workout_date: date = Field(
        description="Date when the workout was performed",
        examples=["2024-01-01"],
    )
    started_at: datetime | None = Field(
        default=None,
        description="Date and time when the workout started",
        examples=["2024-01-01T10:00:00Z"],
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Date and time when the workout was completed",
        examples=["2024-01-01T11:30:00Z"],
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional notes about the workout",
        examples=["Felt strong today, increased weights on squats."],
    )

    @field_validator("completed_at", mode="after")
    @classmethod
    def validate_completed_at(cls, v: datetime | None, info: ValidationInfo) -> datetime | None:
        if (
            v is not None
            and "started_at" in info.data
            and info.data["started_at"] is not None
            and v < info.data["started_at"]
        ):
            raise ValueError("completed_at cannot be earlier than started_at")
        return v


class WorkoutCreate(WorkoutBase):
    """Schema for creating a new workout. All fields are required except description, completed_at, and notes."""  # noqa: E501

    pass


class WorkoutUpdate(BaseModel):
    """Schema for updating an existing workout. All fields are optional."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Name of the workout",
        examples=["Full Body Strength", "Upper Body Hypertrophy"],
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional description of the workout",
        examples=["A comprehensive workout targeting all major muscle groups."],
    )
    workout_date: date | None = Field(
        default=None,
        description="Date when the workout was performed",
        examples=["2024-01-01"],
    )
    started_at: datetime | None = Field(
        default=None,
        description="Date and time when the workout started",
        examples=["2024-01-01T10:00:00Z"],
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Date and time when the workout was completed",
        examples=["2024-01-01T11:30:00Z"],
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional notes about the workout",
        examples=["Felt strong today, increased weights on squats."],
    )

    @field_validator("completed_at", mode="after")
    @classmethod
    def validate_completed_at(
        cls,
        v: datetime | None,
        info: ValidationInfo,
    ) -> datetime | None:
        if (
            v is not None
            and "started_at" in info.data
            and info.data["started_at"] is not None
            and v < info.data["started_at"]
        ):
            raise ValueError("completed_at cannot be earlier than started_at")
        return v


class WorkoutPublic(WorkoutBase):
    """Schema for returning workout data to clients."""

    id: int
    user_id: int | None
    created_at: datetime
    updated_at: datetime
