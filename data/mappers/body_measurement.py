"""Database row validation and mapping for body measurement."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from core.errors.repository import BodyMeasurementRowError
from data.validation import RowValidator
from schemas.body_measurement_schema import BodyMeasurementPublic

if TYPE_CHECKING:
    from datetime import date, datetime
    from decimal import Decimal

_validator = RowValidator(BodyMeasurementRowError)


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


def _parse_body_measurement_row(
    row: dict[str, object],
) -> BodyMeasurementRow:
    """Validate and normalize a raw database row into a typed BodyMeasurementRow."""

    id_value = _validator.require_int(row.get("id"), "id")
    user_id = _validator.require_int(row.get("user_id"), "user_id")
    entry_date = _validator.require_date(row.get("entry_date"), "entry_date")
    notes = _validator.require_optional_str(row.get("notes"), "notes")
    created_at = _validator.require_datetime(row.get("created_at"), "created_at")
    updated_at = _validator.require_datetime(row.get("updated_at"), "updated_at")

    return BodyMeasurementRow(
        id=id_value,
        user_id=user_id,
        entry_date=entry_date,
        neck=_validator.require_optional_decimal(row.get("neck"), "neck"),
        shoulders=_validator.require_optional_decimal(row.get("shoulders"), "shoulders"),
        waist=_validator.require_optional_decimal(row.get("waist"), "waist"),
        chest=_validator.require_optional_decimal(row.get("chest"), "chest"),
        hips=_validator.require_optional_decimal(row.get("hips"), "hips"),
        left_bicep=_validator.require_optional_decimal(row.get("left_bicep"), "left_bicep"),
        right_bicep=_validator.require_optional_decimal(row.get("right_bicep"), "right_bicep"),
        left_forearm=_validator.require_optional_decimal(row.get("left_forearm"), "left_forearm"),
        right_forearm=_validator.require_optional_decimal(row.get("right_forearm"), "right_forearm"),
        left_thigh=_validator.require_optional_decimal(row.get("left_thigh"), "left_thigh"),
        right_thigh=_validator.require_optional_decimal(row.get("right_thigh"), "right_thigh"),
        left_calf=_validator.require_optional_decimal(row.get("left_calf"), "left_calf"),
        right_calf=_validator.require_optional_decimal(row.get("right_calf"), "right_calf"),
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
