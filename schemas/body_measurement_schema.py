from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class BodyMeasurementBase(BaseModel):
    """Base schema for body measurements."""

    entry_date: date = Field(..., description="Date of the body measurement entry")
    neck: Decimal | None = Field(default=None, gt=0, description="Neck circumference in centimeters")
    shoulders: Decimal | None = Field(default=None, gt=0, description="Shoulder circumference in centimeters")
    waist: Decimal | None = Field(default=None, gt=0, description="Waist circumference in centimeters")
    chest: Decimal | None = Field(default=None, gt=0, description="Chest circumference in centimeters")
    hips: Decimal | None = Field(default=None, gt=0, description="Hips circumference in centimeters")
    left_bicep: Decimal | None = Field(
        default=None, gt=0, description="Left bicep circumference in centimeters"
    )
    right_bicep: Decimal | None = Field(
        default=None, gt=0, description="Right bicep circumference in centimeters"
    )
    left_forearm: Decimal | None = Field(
        default=None, gt=0, description="Left forearm circumference in centimeters"
    )
    right_forearm: Decimal | None = Field(
        default=None, gt=0, description="Right forearm circumference in centimeters"
    )
    left_thigh: Decimal | None = Field(
        default=None, gt=0, description="Left thigh circumference in centimeters"
    )
    right_thigh: Decimal | None = Field(
        default=None, gt=0, description="Right thigh circumference in centimeters"
    )
    left_calf: Decimal | None = Field(default=None, gt=0, description="Left calf circumference in centimeters")
    right_calf: Decimal | None = Field(
        default=None, gt=0, description="Right calf circumference in centimeters"
    )
    notes: str | None = Field(default=None, description="Additional notes about the body measurement entry")


class BodyMeasurementCreate(BodyMeasurementBase):
    """Schema for creating a new body measurement entry. All fields are required except the measurements and notes."""  # noqa: E501

    @model_validator(mode="after")
    def validate_at_least_one_measurement(self) -> BodyMeasurementCreate:
        measurement_fields = [
            self.neck,
            self.shoulders,
            self.waist,
            self.chest,
            self.hips,
            self.left_bicep,
            self.right_bicep,
            self.left_forearm,
            self.right_forearm,
            self.left_thigh,
            self.right_thigh,
            self.left_calf,
            self.right_calf,
        ]
        if all(value is None for value in measurement_fields):
            raise ValueError("At least one body measurement must be provided.")
        return self


class BodyMeasurementUpdate(BaseModel):
    """Schema for updating an existing body measurement entry. All fields are optional."""

    entry_date: date | None = Field(default=None, description="Date of the body measurement entry")
    neck: Decimal | None = Field(default=None, gt=0, description="Neck circumference in centimeters")
    shoulders: Decimal | None = Field(default=None, gt=0, description="Shoulder circumference in centimeters")
    waist: Decimal | None = Field(default=None, gt=0, description="Waist circumference in centimeters")
    chest: Decimal | None = Field(default=None, gt=0, description="Chest circumference in centimeters")
    hips: Decimal | None = Field(default=None, gt=0, description="Hips circumference in centimeters")
    left_bicep: Decimal | None = Field(
        default=None, gt=0, description="Left bicep circumference in centimeters"
    )
    right_bicep: Decimal | None = Field(
        default=None, gt=0, description="Right bicep circumference in centimeters"
    )
    left_forearm: Decimal | None = Field(
        default=None, gt=0, description="Left forearm circumference in centimeters"
    )
    right_forearm: Decimal | None = Field(
        default=None, gt=0, description="Right forearm circumference in centimeters"
    )
    left_thigh: Decimal | None = Field(
        default=None, gt=0, description="Left thigh circumference in centimeters"
    )
    right_thigh: Decimal | None = Field(
        default=None, gt=0, description="Right thigh circumference in centimeters"
    )
    left_calf: Decimal | None = Field(default=None, gt=0, description="Left calf circumference in centimeters")
    right_calf: Decimal | None = Field(
        default=None, gt=0, description="Right calf circumference in centimeters"
    )
    notes: str | None = Field(default=None, description="Additional notes about the body measurement entry")


class BodyMeasurementPublic(BodyMeasurementBase):
    """Schema for returning body measurement entry data to clients. Includes all fields from BodyMeasurementBase plus id, user_id, created_at, and updated_at."""  # noqa: E501

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
