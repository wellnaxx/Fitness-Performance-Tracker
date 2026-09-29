"""Database row validation and mapping for body weight entry."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TypedDict

from core.errors.repository import BodyWeightEntryRowError
from schemas.body_weight_entry_schema import BodyWeightEntryPublic


class BodyWeightEntryRow(TypedDict):
    id: int
    user_id: int
    weight: Decimal
    entry_date: date
    created_at: datetime


def _parse_body_weight_entry_row(
    row: dict[str, object],
) -> BodyWeightEntryRow:
    """Validate and normalize a raw database row into a typed BodyWeightEntryRow."""
    id_value = row.get("id")
    user_id = row.get("user_id")
    weight = row.get("weight")
    entry_date = row.get("entry_date")
    created_at = row.get("created_at")

    if not isinstance(id_value, int):
        raise BodyWeightEntryRowError.invalid_type("id", "int")
    if not isinstance(user_id, int):
        raise BodyWeightEntryRowError.invalid_type("user_id", "int")
    if not isinstance(weight, (Decimal, int, float)):
        raise BodyWeightEntryRowError.invalid_type("weight", "numeric")
    if not isinstance(entry_date, date):
        raise BodyWeightEntryRowError.invalid_type("entry_date", "date")
    if not isinstance(created_at, datetime):
        raise BodyWeightEntryRowError.invalid_type("created_at", "datetime")

    return BodyWeightEntryRow(
        id=id_value,
        user_id=user_id,
        weight=Decimal(str(weight)),
        entry_date=entry_date,
        created_at=created_at,
    )


def map_body_weight_entry(
    row: dict[str, object],
) -> BodyWeightEntryPublic:
    """Convert a raw database row into a validated BodyWeightEntryPublic model."""
    entry_row = _parse_body_weight_entry_row(row)
    return BodyWeightEntryPublic.model_validate(entry_row)
