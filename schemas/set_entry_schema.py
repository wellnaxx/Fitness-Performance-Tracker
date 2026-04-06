from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SetEntryBase(BaseModel):
    workout_exercise_id: int = Field(description="ID of the parent workout exercise")
    set_number: int = Field(gt=0, description="Set number within the exercise")
    reps: int = Field(ge=0, description="Number of repetitions completed")
    weight: float = Field(ge=0, description="Weight used for the set")
    rpe: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="Rate of perceived exertion for the set",
    )
    is_warmup: bool = Field(default=False, description="Whether the set is a warm-up set")
    completed: bool = Field(default=True, description="Whether the set was completed")


class SetEntryCreate(SetEntryBase):
    pass


class SetEntryUpdate(BaseModel):
    set_number: int | None = Field(default=None, gt=0)
    reps: int | None = Field(default=None, ge=0)
    weight: float | None = Field(default=None, ge=0)
    rpe: int | None = Field(default=None, ge=1, le=10)
    is_warmup: bool | None = None
    completed: bool | None = None


class SetEntryPublic(SetEntryBase):
    id: int
    created_at: datetime
