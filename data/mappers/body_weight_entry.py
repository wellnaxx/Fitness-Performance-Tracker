"""Database row validation and mapping for body weight entry."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

from core.errors.repository import BodyWeightEntryRowError
from data.validation import RowValidator
from schemas.body_weight_entry_schema import BodyWeightEntryPublic

if TYPE_CHECKING:
    from datetime import date, datetime

_validator = RowValidator(BodyWeightEntryRowError)


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

    id_value = _validator.require_int(row.get("id"), "id")
    user_id = _validator.require_int(row.get("user_id"), "user_id")
    weight = _validator.require_numeric(row.get("weight"), "weight")
    entry_date = _validator.require_date(row.get("entry_date"), "entry_date")
    created_at = _validator.require_datetime(row.get("created_at"), "created_at")

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
