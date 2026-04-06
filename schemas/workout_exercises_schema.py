from __future__ import annotations

from pydantic import BaseModel, Field


class WorkoutExerciseBase(BaseModel):
    """Base workout exercise model with common fields."""

    workout_id: int = Field(..., description="ID of the associated workout")
    exercise_id: int = Field(..., description="ID of the associated exercise")
    order_index: int = Field(
        ge=0,
        description="Index indicating the position of the exercise in the workout",
        examples=[0, 1, 2],
    )
    rest_seconds: int | None = Field(
        default=None,
        ge=0,
        description="Suggested rest time in seconds between sets (optional)",
        examples=[60],
    )
    notes: str | None = Field(
        default=None,
        max_length=500,
        description="Optional notes about this exercise within the workout",
        examples=["Felt strong today, increased weight on last set."],
    )


class WorkoutExerciseCreate(WorkoutExerciseBase):
    """Schema for creating a new workout exercise. All fields are required except weight and notes."""

    pass


class WorkoutExerciseUpdate(BaseModel):
    """Schema for updating an exercise entry inside a workout."""

    exercise_id: int | None = Field(
        default=None,
        description="ID of the associated exercise",
    )
    order_index: int | None = Field(
        default=None,
        ge=0,
        description="Position of the exercise within the workout",
    )
    rest_seconds: int | None = Field(
        default=None,
        ge=0,
        description="Suggested rest time in seconds between sets",
        examples=[60],
    )
    notes: str | None = Field(
        default=None,
        max_length=500,
        description="Optional notes about this exercise within the workout",
        examples=["Focus on controlled tempo."],
    )


class WorkoutExercisePublic(WorkoutExerciseBase):
    """Schema for returning workout exercise data to clients."""

    id: int
