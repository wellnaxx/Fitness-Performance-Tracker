from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MealItemBase(BaseModel):
    """Shared fields for a food item inside a meal."""

    name: str = Field(
        min_length=1,
        max_length=100,
        description="Name of the food item",
        examples=["Chicken Breast", "Rice", "Olive Oil"],
    )
    serving_size: Decimal | None = Field(
        default=None,
        ge=0,
        description="Serving size of the food item",
        examples=[150],
    )
    calories: Decimal = Field(ge=0, description="Calories in the food item")
    protein: Decimal = Field(ge=0, description="Protein in grams")
    carbs: Decimal = Field(ge=0, description="Carbohydrates in grams")
    fats: Decimal = Field(ge=0, description="Fats in grams")


class MealItemCreate(MealItemBase):
    meal_id: int = Field(description="ID of the parent meal")


class MealItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    serving_size: Decimal | None = Field(default=None, ge=0)
    calories: Decimal | None = Field(default=None, ge=0)
    protein: Decimal | None = Field(default=None, ge=0)
    carbs: Decimal | None = Field(default=None, ge=0)
    fats: Decimal | None = Field(default=None, ge=0)


class MealItemPublic(MealItemBase):
    id: int
    meal_id: int
    created_at: datetime
