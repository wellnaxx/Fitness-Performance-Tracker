"""Database row validation and mapping for user."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from core.errors.repository import UserRowError
from data.validation import RowValidator
from schemas.user_schema import UserInternal

if TYPE_CHECKING:
    from datetime import date, datetime

_validator = RowValidator(UserRowError)


class UserRow(TypedDict):
    id: int
    username: str
    first_name: str
    last_name: str
    date_of_birth: date
    email: str
    password_hash: str
    profile_picture_url: str | None
    token_version: int
    weight_unit_preference: str
    measurement_unit_preference: str
    created_at: datetime
    updated_at: datetime


def _parse_user_row(row: dict[str, object]) -> UserRow:
    """Validate and normalize a raw database row into a typed UserRow."""

    id_value = _validator.require_int(row.get("id"), "id")
    username = _validator.require_str(row.get("username"), "username")
    first_name = _validator.require_str(row.get("first_name"), "first_name")
    last_name = _validator.require_str(row.get("last_name"), "last_name")
    date_of_birth = _validator.require_date(row.get("date_of_birth"), "date_of_birth")
    email = _validator.require_str(row.get("email"), "email")
    password_hash = _validator.require_str(row.get("password_hash"), "password_hash")
    profile_picture_url = _validator.require_optional_str(row.get("profile_picture_url"), "profile_picture_url")
    token_version = _validator.require_int(row.get("token_version"), "token_version")
    weight_unit_preference = _validator.require_str(row.get("weight_unit_preference"), "weight_unit_preference")
    measurement_unit_preference = _validator.require_str(
        row.get("measurement_unit_preference"), "measurement_unit_preference"
    )
    created_at = _validator.require_datetime(row.get("created_at"), "created_at")
    updated_at = _validator.require_datetime(row.get("updated_at"), "updated_at")

    return UserRow(
        id=id_value,
        username=username,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        email=email,
        password_hash=password_hash,
        profile_picture_url=profile_picture_url,
        token_version=token_version,
        weight_unit_preference=weight_unit_preference,
        measurement_unit_preference=measurement_unit_preference,
        created_at=created_at,
        updated_at=updated_at,
    )


def map_user(row: dict[str, object]) -> UserInternal:
    """Convert a raw database row into a validated UserInternal model."""
    user_row = _parse_user_row(row)
    return UserInternal.model_validate(user_row)
