from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class BodyWeightEntryBase(BaseModel):
    """Base schema for body weight entries."""

    weight: Decimal = Field(..., gt=0, description="Body weight in kilograms")
    entry_date: date = Field(..., description="Date of the body weight entry")


class BodyWeightEntryCreate(BodyWeightEntryBase):
    """Schema for creating a new body weight entry. All fields are required."""

    pass


class BodyWeightEntryUpdate(BaseModel):
    """Schema for updating an existing body weight entry. All fields are optional."""

    weight: Decimal | None = Field(default=None, gt=0, description="Body weight in kilograms")
    entry_date: date | None = Field(default=None, description="Date of the body weight entry")


class BodyWeightEntryPublic(BodyWeightEntryBase):
    """Schema for returning body weight entry data to clients. Includes all fields from BodyWeightEntryBase plus id, user_id, created_at, and updated_at."""  # noqa: E501

    id: int
    user_id: int
    created_at: datetime
