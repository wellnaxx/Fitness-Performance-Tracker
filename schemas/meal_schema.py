from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from utils.validators import validate_meal_type


class MealBase(BaseModel):
    """Base meal model with common fields."""
    name: str = Field(
        min_length=1,
        max_length=100,
        description="Name of the meal",
        examples=["Chicken Salad", "Oatmeal with Berries"],
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional description of the meal",
        examples=["A healthy meal with lean protein and vegetables."],
    )
    eaten_at: datetime = Field(
        description="Date and time when the meal was consumed",
        examples=["2024-01-01T12:30:00Z"],
    )
    meal_type: str = Field(
        description="Time of day when the meal was consumed (e.g., 'Breakfast', 'Lunch', 'Dinner', 'Snack')",
        examples=["Breakfast", "Lunch", "Dinner", "Snack"],
    )
    notes: str | None = Field(
        default=None,
        max_length=500,
        description="Optional notes about the meal",
        examples=["Felt very satisfied after this meal."],
    )

    @field_validator("meal_type")
    @classmethod
    def validate_meal_type_field(cls, v: str) -> str:
        return validate_meal_type(v)


class MealCreate(MealBase):
    """Schema for creating a new meal. All fields are required except description."""
    pass


class MealUpdate(BaseModel):
    """Schema for updating an existing meal. All fields are optional."""
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Name of the meal",
        examples=["Chicken Salad", "Oatmeal with Berries"],
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional description of the meal",
        examples=["A healthy meal with lean protein and vegetables."],
    )
    eaten_at: datetime | None = Field(
        default=None,
        description="Date and time when the meal was consumed",
        examples=["2024-01-01T12:30:00Z"],
    )
    meal_type: str | None = Field(
        default=None,
        description="Time of day when the meal was consumed (e.g., 'Breakfast', 'Lunch', 'Dinner', 'Snack')",
        examples=["Breakfast", "Lunch", "Dinner", "Snack"],
    )

    notes: str | None = Field(
        default=None,
        max_length=500,
        description="Optional notes about the meal",
        examples=["Felt very satisfied after this meal."],
    )

    @field_validator("meal_type")
    @classmethod
    def validate_meal_type_field(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_meal_type(v)
        return v


class MealPublic(MealBase):
    """Schema for returning meal data to clients. Includes all fields from MealBase plus id, user_id, created_at, and updated_at."""  # noqa: E501
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
