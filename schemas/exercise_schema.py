from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ExerciseBase(BaseModel):
    """Base exercise model with common fields."""

    name: str = Field(
        min_length=1,
        max_length=100,
        description="Name of the exercise",
        examples=["Bench Press", "Squat", "Deadlift"],
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional description of the exercise",
        examples=["A compound exercise targeting the chest muscles."],
    )
    muscle_group: str = Field(
        max_length=50,
        description="Primary muscle group targeted by the exercise",
        examples=["Chest", "Legs", "Back"],
    )
    equipment: str | None = Field(
        default=None,
        max_length=50,
        description="Equipment needed for the exercise",
        examples=["Barbell", "Dumbbell", "Machine"],
    )
    is_compound: bool = Field(
        description="Indicates if the exercise is a compound movement",
        examples=[True, False],
    )


class ExerciseCreate(ExerciseBase):
    """Schema for creating a new exercise. All fields are required except description."""


class ExerciseUpdate(BaseModel):
    """Schema for updating an existing exercise. All fields are optional."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Name of the exercise",
        examples=["Bench Press", "Squat", "Deadlift"],
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional description of the exercise",
        examples=["A compound exercise targeting the chest muscles."],
    )
    muscle_group: str | None = Field(
        default=None,
        max_length=50,
        description="Primary muscle group targeted by the exercise",
        examples=["Chest", "Legs", "Back"],
    )
    equipment: str | None = Field(
        default=None,
        max_length=50,
        description="Equipment needed for the exercise",
        examples=["Barbell", "Dumbbell", "Machine"],
    )
    is_compound: bool | None = Field(
        default=None,
        description="Indicates if the exercise is a compound movement",
        examples=[True, False],
    )


class ExercisePublic(ExerciseBase):
    """Schema for returning exercise data to clients."""

    id: int = Field(description="Unique identifier for the exercise")
    is_custom: bool = Field(
        description="Indicates if the exercise is user-created (custom) or from the predefined list",
        examples=[True, False],
    )
    created_by: int | None = Field(
        default=None, description="User ID of the creator if it's a custom exercise, otherwise null"
    )
    created_at: datetime = Field(description="Timestamp when the exercise was created")
    updated_at: datetime = Field(description="Timestamp when the exercise was last updated")
