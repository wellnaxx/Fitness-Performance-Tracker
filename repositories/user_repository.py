"""
User Repository - Data Access Layer for User operations.

This module handles all database interactions for the User entity.
It delegates database row validation and conversion to the dedicated mapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from core.errors.repository import UserRepositoryError
from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from data.mappers.user import map_user
from data.queries import QUERIES

if TYPE_CHECKING:
    from schemas.user_schema import UserCreate, UserInternal


class UserRepository:
    """
    Repository for User database operations.

    Responsibilities:
    - Execute SQL queries related to users
    - Convert database row dicts to UserInternal models
    - Handle all user-related database logic
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
        sql = QUERIES.users.create
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
                QUERIES.users.username_exists,
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
                QUERIES.users.email_exists,
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
        row = fetch_one(QUERIES.users.get_by_id, (user_id,))
        if row is None:
            return None
        return map_user(row)

    def get_by_username(self, username: str) -> UserInternal | None:
        """
        Retrieve a user by username.

        Args:
            username: Username value.

        Returns:
            The user if found, otherwise None.
        """
        row = fetch_one(QUERIES.users.get_by_username, (username,))
        if row is None:
            return None
        return map_user(row)

    def get_by_email(self, email: str) -> UserInternal | None:
        """
        Retrieve a user by email address.

        Args:
            email: Email value.

        Returns:
            The user if found, otherwise None.
        """
        row = fetch_one(QUERIES.users.get_by_email, (email,))
        if row is None:
            return None
        return map_user(row)

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
            QUERIES.users.get_all,
            (safe_limit, safe_offset),
        )
        return [map_user(row) for row in rows]

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
        sql = QUERIES.users.update.format(set_clause=set_clause)
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
            QUERIES.users.set_profile_picture_url,
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
            QUERIES.users.set_weight_unit_preference,
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
            QUERIES.users.set_measurement_unit_preference,
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
                QUERIES.users.update_password,
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
                QUERIES.users.bump_token_version,
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
        return execute_write(QUERIES.users.delete, (user_id,)) > 0
