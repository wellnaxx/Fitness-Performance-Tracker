from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class BodyWeightEntryBase(BaseModel):
    """A positive kilogram weight fitting DECIMAL(5,2), recorded on a measurement date."""

    weight: Decimal = Field(..., gt=0, max_digits=5, decimal_places=2, description="Body weight in kilograms")
    entry_date: date = Field(..., description="Date of the body weight entry")


class BodyWeightEntryCreate(BodyWeightEntryBase):
    """Required weight/date values; the service enforces one entry per user and date."""


class BodyWeightEntryUpdate(BaseModel):
    """Partial weight/date changes; omitted and None-valued fields keep their stored values."""

    weight: Decimal | None = Field(
        default=None, gt=0, max_digits=5, decimal_places=2, description="Body weight in kilograms"
    )
    entry_date: date | None = Field(default=None, description="Date of the body weight entry")


class BodyWeightEntryPublic(BodyWeightEntryBase):
    """Persisted weight/date values with their assigned ID, owner ID, and creation timestamp."""

    id: int
    user_id: int
    created_at: datetime
