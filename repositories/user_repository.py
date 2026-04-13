"""
User Repository - Data Access Layer for User operations.

This module handles all database interactions for the User entity.
It translates between database rows (now dicts) and Pydantic models.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Final, TypedDict

from core.errors.repository import UserRepositoryError, UserRowError
from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from schemas.user_schema import UserCreate, UserInternal


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


class UserRepository:
    """
    Repository for User database operations.

    Responsibilities:
    - Execute SQL queries related to users
    - Convert database row dicts to UserInternal models
    - Handle all user-related database logic
    """

    _BASE_SELECT: Final[str] = """
        SELECT id, username, first_name, last_name, date_of_birth, email, password_hash,
               profile_picture_url, token_version, weight_unit_preference, measurement_unit_preference,
               created_at, updated_at
        FROM users
    """

    _PROFILE_UPDATE_WHITELIST: Final[set[str]] = {
        "first_name",
        "last_name",
        "date_of_birth",
        "email",
        "profile_picture_url",
        "weight_unit_preference",
        "measurement_unit_preference",
    }

    def create(self, user_data: UserCreate, password_hash: str) -> UserInternal:
        """
        Create a new user account.

        Args:
            user_data: User creation payload.
            password_hash: Pre-hashed password to persist.

        Returns:
            The newly created internal user model.

        Raises:
            UserRepositoryError: If the inserted user cannot be retrieved afterwards.
        """
        sql = """
            INSERT INTO users
            (first_name, last_name, date_of_birth, email, username, password_hash)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        user_id = execute_insert(
            sql,
            (
                user_data.first_name,
                user_data.last_name,
                user_data.date_of_birth,
                user_data.email,
                user_data.username,
                password_hash,
            ),
        )

        user = self.get_by_id(user_id)
        if user is None:
            raise UserRepositoryError.inserted_missing(user_id)
        return user

    def username_exists(self, username: str) -> bool:
        """
        Check whether a username already exists.

        Args:
            username: Username to look up.

        Returns:
            True if a matching user exists, otherwise False.
        """
        return (
            fetch_one(
                "SELECT 1 FROM users WHERE username = %s LIMIT 1",
                (username,),
            )
            is not None
        )

    def email_exists(self, email: str) -> bool:
        """
        Check whether an email address already exists.

        Args:
            email: Email address to look up.

        Returns:
            True if a matching user exists, otherwise False.
        """
        return (
            fetch_one(
                "SELECT 1 FROM users WHERE email = %s LIMIT 1",
                (email,),
            )
            is not None
        )

    def get_by_id(self, user_id: int) -> UserInternal | None:
        """
        Retrieve a user by database ID.

        Args:
            user_id: User ID.

        Returns:
            The user if found, otherwise None.
        """
        row = fetch_one(f"{self._BASE_SELECT} WHERE id = %s", (user_id,))
        if row is None:
            return None
        return self._row_to_user(row)

    def get_by_username(self, username: str) -> UserInternal | None:
        """
        Retrieve a user by username.

        Args:
            username: Username value.

        Returns:
            The user if found, otherwise None.
        """
        row = fetch_one(f"{self._BASE_SELECT} WHERE username = %s", (username,))
        if row is None:
            return None
        return self._row_to_user(row)

    def get_by_email(self, email: str) -> UserInternal | None:
        """
        Retrieve a user by email address.

        Args:
            email: Email value.

        Returns:
            The user if found, otherwise None.
        """
        row = fetch_one(f"{self._BASE_SELECT} WHERE email = %s", (email,))
        if row is None:
            return None
        return self._row_to_user(row)

    def get_all(self, limit: int = 100, offset: int = 0) -> list[UserInternal]:
        """
        Retrieve users with pagination.

        Args:
            limit: Maximum number of rows to return.
            offset: Number of rows to skip.

        Returns:
            Users ordered from newest to oldest.
        """
        safe_limit = max(1, min(limit, 1000))
        safe_offset = max(0, offset)

        rows = fetch_all(
            f"{self._BASE_SELECT} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (safe_limit, safe_offset),
        )
        return [self._row_to_user(row) for row in rows]

    def update(self, user_id: int, **updates: object) -> UserInternal | None:
        """
        Patch-update allowed profile fields (whitelist-enforced).

        Unknown fields raise UserRepositoryError. None values are skipped.
        """
        if not updates:
            return self.get_by_id(user_id)

        unknown = set(updates.keys()) - self._PROFILE_UPDATE_WHITELIST
        if unknown:
            raise UserRepositoryError.invalid_update_fields(unknown)

        filtered: dict[str, object] = {key: value for key, value in updates.items() if value is not None}
        if not filtered:
            return self.get_by_id(user_id)

        set_clause = ", ".join(f"{field} = %s" for field in filtered)
        sql = f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        execute_write(sql, (*filtered.values(), user_id))

        user = self.get_by_id(user_id)
        if user is None:
            raise UserRepositoryError.updated_missing(user_id)
        return user

    def set_profile_picture_url(
        self,
        user_id: int,
        profile_picture_url: str | None,
    ) -> UserInternal | None:
        """
        Set or clear the profile picture URL for a user.

        Args:
            user_id: User ID.
            profile_picture_url: New URL value, or None to clear it.

        Returns:
            The updated user if found, otherwise None.
        """
        execute_write(
            "UPDATE users SET profile_picture_url = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (profile_picture_url, user_id),
        )
        return self.get_by_id(user_id)

    def set_weight_unit_preference(
        self,
        user_id: int,
        weight_unit_preference: str,
    ) -> UserInternal | None:
        """
        Update the user's preferred weight unit.

        Args:
            user_id: User ID.
            weight_unit_preference: New weight unit value.

        Returns:
            The updated user if found, otherwise None.
        """
        execute_write(
            "UPDATE users SET weight_unit_preference = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (weight_unit_preference, user_id),
        )
        return self.get_by_id(user_id)

    def set_measurement_unit_preference(
        self,
        user_id: int,
        measurement_unit_preference: str,
    ) -> UserInternal | None:
        """
        Update the user's preferred body measurement unit.

        Args:
            user_id: User ID.
            measurement_unit_preference: New measurement unit value.

        Returns:
            The updated user if found, otherwise None.
        """
        execute_write(
            "UPDATE users SET measurement_unit_preference = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (measurement_unit_preference, user_id),
        )
        return self.get_by_id(user_id)

    def update_password(self, user_id: int, new_password_hash: str) -> bool:
        """
        Update the stored password hash and revoke existing tokens.

        Args:
            user_id: User ID.
            new_password_hash: New password hash.

        Returns:
            True if a row was updated, otherwise False.
        """
        return (
            execute_write(
                "UPDATE users SET password_hash = %s, "
                "token_version = token_version + 1, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (new_password_hash, user_id),
            )
            > 0
        )

    def bump_token_version(self, user_id: int) -> bool:
        """
        Increment the token version for a user.

        Args:
            user_id: User ID.

        Returns:
            True if a row was updated, otherwise False.
        """
        return (
            execute_write(
                "UPDATE users SET token_version = token_version + 1, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (user_id,),
            )
            > 0
        )

    def delete(self, user_id: int) -> bool:
        """
        Delete a user by ID.

        Args:
            user_id: User ID.

        Returns:
            True if a row was deleted, otherwise False.
        """
        return execute_write("DELETE FROM users WHERE id = %s", (user_id,)) > 0

    @staticmethod
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

    @classmethod
    def _row_to_user(cls, row: dict[str, object]) -> UserInternal:
        """Convert a raw database row into a validated UserInternal model."""
        user_row = cls._parse_user_row(row)
        return UserInternal.model_validate(user_row)
