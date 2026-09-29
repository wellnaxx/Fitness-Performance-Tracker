"""Database row validation and mapping for body measurement."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TypedDict

from core.errors.repository import BodyMeasurementRowError
from schemas.body_measurement_schema import BodyMeasurementPublic


class BodyMeasurementRow(TypedDict):
    id: int
    user_id: int
    entry_date: date
    neck: Decimal | None
    shoulders: Decimal | None
    waist: Decimal | None
    chest: Decimal | None
    hips: Decimal | None
    left_bicep: Decimal | None
    right_bicep: Decimal | None
    left_forearm: Decimal | None
    right_forearm: Decimal | None
    left_thigh: Decimal | None
    right_thigh: Decimal | None
    left_calf: Decimal | None
    right_calf: Decimal | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


def _to_decimal_or_none(field_name: str, value: object) -> Decimal | None:
    """Convert a numeric database value into Decimal while preserving None."""
    if value is None:
        return None
    if not isinstance(value, (Decimal, int, float)):
        raise BodyMeasurementRowError.invalid_type(field_name, "numeric | None")
    return Decimal(str(value))


def _parse_body_measurement_row(
    row: dict[str, object],
) -> BodyMeasurementRow:
    """Validate and normalize a raw database row into a typed BodyMeasurementRow."""
    id_value = row.get("id")
    user_id = row.get("user_id")
    entry_date = row.get("entry_date")
    notes = row.get("notes")
    created_at = row.get("created_at")
    updated_at = row.get("updated_at")

    if not isinstance(id_value, int):
        raise BodyMeasurementRowError.invalid_type("id", "int")
    if not isinstance(user_id, int):
        raise BodyMeasurementRowError.invalid_type("user_id", "int")
    if not isinstance(entry_date, date):
        raise BodyMeasurementRowError.invalid_type("entry_date", "date")
    if notes is not None and not isinstance(notes, str):
        raise BodyMeasurementRowError.invalid_type("notes", "str | None")
    if not isinstance(created_at, datetime):
        raise BodyMeasurementRowError.invalid_type("created_at", "datetime")
    if not isinstance(updated_at, datetime):
        raise BodyMeasurementRowError.invalid_type("updated_at", "datetime")

    return BodyMeasurementRow(
        id=id_value,
        user_id=user_id,
        entry_date=entry_date,
        neck=_to_decimal_or_none("neck", row.get("neck")),
        shoulders=_to_decimal_or_none("shoulders", row.get("shoulders")),
        waist=_to_decimal_or_none("waist", row.get("waist")),
        chest=_to_decimal_or_none("chest", row.get("chest")),
        hips=_to_decimal_or_none("hips", row.get("hips")),
        left_bicep=_to_decimal_or_none("left_bicep", row.get("left_bicep")),
        right_bicep=_to_decimal_or_none("right_bicep", row.get("right_bicep")),
        left_forearm=_to_decimal_or_none("left_forearm", row.get("left_forearm")),
        right_forearm=_to_decimal_or_none("right_forearm", row.get("right_forearm")),
        left_thigh=_to_decimal_or_none("left_thigh", row.get("left_thigh")),
        right_thigh=_to_decimal_or_none("right_thigh", row.get("right_thigh")),
        left_calf=_to_decimal_or_none("left_calf", row.get("left_calf")),
        right_calf=_to_decimal_or_none("right_calf", row.get("right_calf")),
        notes=notes,
        created_at=created_at,
        updated_at=updated_at,
    )


def map_body_measurement(
    row: dict[str, object],
) -> BodyMeasurementPublic:
    """Convert a raw database row into a validated BodyMeasurementPublic model."""
    measurement_row = _parse_body_measurement_row(row)
    return BodyMeasurementPublic.model_validate(measurement_row)
