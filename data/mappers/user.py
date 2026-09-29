"""Database row validation and mapping for user."""

from __future__ import annotations

from datetime import date, datetime
from typing import TypedDict

from core.errors.repository import UserRowError
from schemas.user_schema import UserInternal


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
    id_value = row.get("id")
    username = row.get("username")
    first_name = row.get("first_name")
    last_name = row.get("last_name")
    date_of_birth = row.get("date_of_birth")
    email = row.get("email")
    password_hash = row.get("password_hash")
    profile_picture_url = row.get("profile_picture_url")
    token_version = row.get("token_version")
    weight_unit_preference = row.get("weight_unit_preference")
    measurement_unit_preference = row.get("measurement_unit_preference")
    created_at = row.get("created_at")
    updated_at = row.get("updated_at")

    if not isinstance(id_value, int):
        raise UserRowError.invalid_type("id", "int")
    if not isinstance(username, str):
        raise UserRowError.invalid_type("username", "str")
    if not isinstance(first_name, str):
        raise UserRowError.invalid_type("first_name", "str")
    if not isinstance(last_name, str):
        raise UserRowError.invalid_type("last_name", "str")
    if not isinstance(date_of_birth, date):
        raise UserRowError.invalid_type("date_of_birth", "date")
    if not isinstance(email, str):
        raise UserRowError.invalid_type("email", "str")
    if not isinstance(password_hash, str):
        raise UserRowError.invalid_type("password_hash", "str")
    if profile_picture_url is not None and not isinstance(profile_picture_url, str):
        raise UserRowError.invalid_type("profile_picture_url", "str | None")
    if not isinstance(token_version, int):
        raise UserRowError.invalid_type("token_version", "int")
    if not isinstance(weight_unit_preference, str):
        raise UserRowError.invalid_type("weight_unit_preference", "str")
    if not isinstance(measurement_unit_preference, str):
        raise UserRowError.invalid_type("measurement_unit_preference", "str")
    if not isinstance(created_at, datetime):
        raise UserRowError.invalid_type("created_at", "datetime")
    if not isinstance(updated_at, datetime):
        raise UserRowError.invalid_type("updated_at", "datetime")

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
